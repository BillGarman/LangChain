"""Wrapper around a Power BI endpoint."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, List

import aiohttp
import requests
from aiohttp.http_exceptions import HttpProcessingError
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import ChainedTokenCredential
from azure.identity._internal import InteractiveCredential

_LOGGER = logging.getLogger(__name__)


@dataclass
class PowerBIDataset:
    """Create PowerBI engine from dataset ID and credential or token.

    Use either the credential or a supplied token to authenticate. If both are supplied the credential is used to generate a token.
    The impersonated_user_name is the UPN of a user to be impersonated. If the model is not RLS enabled, this will be ignored.
    """

    group_id: str | None
    dataset_id: str
    table_names: list[str]
    credential: ChainedTokenCredential | InteractiveCredential | None = None
    token: str | None = None
    impersonated_user_name: str | None = None
    sample_rows_in_table_info: int = field(default=1)
    aiosession: aiohttp.ClientSession | None = field(default=None)
    request_url: str = "https://api.powerbi.com/v1.0/myorg/datasets/"
    schemas: dict[str, str] = field(default={}, init=False)

    def __post_init__(self) -> None:
        """Checks the init.

        Whether a token or credential is set
        Whether the sample rows are a positive int
        Constructs the request_url
        """
        assert self.token or self.credential
        if self.sample_rows_in_table_info < 1:
            self.sample_rows_in_table_info = 1
        if self.group_id:
            self.request_url = f"{self.request_url}/{self.group_id}/datasets/{self.dataset_id}/executeQueries"  # noqa: E501 # pylint: disable=C0301
        else:
            self.request_url = f"{self.request_url}/{self.dataset_id}/executeQueries"  # noqa: E501 # pylint: disable=C0301

    @property
    def headers(self) -> dict[str, str]:
        """Get the token."""
        token = None
        if self.token:
            token = self.token
        if self.credential:
            token = self.credential.get_token(
                "https://analysis.windows.net/powerbi/api/.default"
            ).token
        if not token:
            raise ClientAuthenticationError("No credential or token supplied.")

        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        }

    def get_table_names(self) -> Iterable[str]:
        """Get names of tables available."""
        return self.table_names

    def get_schemas(self) -> str:
        """Get the available schema's."""
        if self.schemas:
            return ", ".join([f"{key}: {value}" for key, value in self.schemas.items()])
        else:
            return "No known schema's yet. Use the schema_powerbi tool first."

    @property
    def table_info(self) -> str:
        """Information about all tables in the database."""
        return self.get_table_info()

    def _get_tables_to_query(
        self, table_names: List[str] | str | None = None
    ) -> list[str]:
        """Get the tables names that need to be queried."""
        if table_names is not None:
            if (
                isinstance(table_names, list)
                and len(table_names) > 0
                and table_names[0] != ""
            ):
                return table_names
            if isinstance(table_names, str) and table_names != "":
                return [table_names]
        return self.table_names

    def _get_tables_todo(self, tables_todo: list[str]) -> list[str]:
        for table in tables_todo:
            if table in self.schemas:
                tables_todo.remove(table)
        return tables_todo

    def _get_schema_for_tables(self, table_names: list[str]) -> str:
        """Create a string of the table schemas for the supplied tables."""
        schemas = [
            schema for table, schema in self.schemas.items() if table in table_names
        ]
        return ", ".join(schemas)

    def get_table_info(self, table_names: List[str] | str | None = None) -> str:
        """Get information about specified tables."""
        tables_requested = self._get_tables_to_query(table_names)
        tables_todo = self._get_tables_todo(tables_requested)
        for table in tables_todo:
            try:
                result = self.run(
                    f"EVALUATE TOPN({self.sample_rows_in_table_info}, {table})"
                )
            except requests.exceptions.Timeout:
                _LOGGER.warning("Timeout while getting table info for %s", table)
                continue
            except requests.exceptions.HTTPError as err:
                _LOGGER.warning(
                    "HTTP error while getting table info for %s: %s", table, err
                )
                return "Error with the connection to PowerBI, please review your authentication credentials."  # noqa: E501 # pylint: disable=C0301
            self.schemas[table] = json_to_md(result["results"][0]["tables"][0]["rows"])
        return self._get_schema_for_tables(tables_requested)

    async def aget_table_info(self, table_names: List[str] | str | None = None) -> str:
        """Get information about specified tables."""
        tables_requested = self._get_tables_to_query(table_names)
        tables_todo = self._get_tables_todo(tables_requested)
        for table in tables_todo:
            try:
                result = await self.arun(
                    f"EVALUATE TOPN({self.sample_rows_in_table_info}, {table})"
                )
            except aiohttp.ServerTimeoutError:
                _LOGGER.warning("Timeout while getting table info for %s", table)
                continue
            except HttpProcessingError as err:
                _LOGGER.warning(
                    "HTTP error while getting table info for %s: %s", table, err
                )
                return "Error with the connection to PowerBI, please review your authentication credentials."  # noqa: E501 # pylint: disable=C0301
            self.schemas[table] = json_to_md(result["results"][0]["tables"][0]["rows"])
        return self._get_schema_for_tables(tables_requested)

    def run(self, command: str) -> Any:
        """Execute a DAX command and return a json representing the results."""

        result = requests.post(
            self.request_url,
            json={
                "queries": [{"query": command}],
                "impersonatedUserName": self.impersonated_user_name,
                "serializerSettings": {"includeNulls": True},
            },
            headers=self.headers,
            timeout=10,
        )
        result.raise_for_status()
        return result.json()

    async def arun(self, command: str) -> Any:
        """Execute a DAX command and return the result asynchronously."""
        json_content = (
            {
                "queries": [{"query": command}],
                "impersonatedUserName": self.impersonated_user_name,
                "serializerSettings": {"includeNulls": True},
            },
        )
        if self.aiosession:
            async with self.aiosession.post(
                self.request_url, headers=self.headers, json=json_content, timeout=10
            ) as response:
                response.raise_for_status()
                response_json = await response.json()
                return response_json
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.request_url, headers=self.headers, json=json_content, timeout=10
            ) as response:
                response.raise_for_status()
                response_json = await response.json()
                return response_json


def json_to_md(
    json_contents: list[dict[str, str | int | float]], table_name: str | None = None
) -> str:
    """Converts a JSON object to a markdown table."""
    output_md = ""
    headers = json_contents[0].keys()
    for header in headers:
        header.replace("[", ".").replace("]", "")
        if table_name:
            header.replace(f"{table_name}.", "")
        output_md += f"| {header} "
    output_md += "|\n"
    for row in json_contents:
        for value in row.values():
            output_md += f"| {value} "
        output_md += "|\n"
    return output_md
