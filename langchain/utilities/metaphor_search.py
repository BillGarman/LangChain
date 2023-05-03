"""Util that calls Metaphor Search API.

In order to set this up, follow instructions at:
"""
from typing import Dict, List

import requests
from pydantic import BaseModel, Extra, root_validator

from langchain.utils import get_from_dict_or_env

METAPHOR_API_URL = "https://api.metaphor.systems"


class MetaphorSearchAPIWrapper(BaseModel):
    """Wrapper for Metaphor Search API.
    """

    metaphor_api_key: str
    k: int = 10

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    def _metaphor_search_results(self, query: str, num_results: int) -> List[dict]:
        headers = {"X-Api-Key": self.metaphor_api_key}
        params = {
            "numResults": num_results,
            "query": query
        }
        response = requests.post(
            f"{METAPHOR_API_URL}/search", headers=headers, json=params  # type: ignore
        )

        response.raise_for_status()
        search_results = response.json()
        print(search_results)
        return search_results["results"]

    @root_validator(pre=True)
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and endpoint exists in environment."""
        metaphor_api_key = get_from_dict_or_env(
            values, "metaphor_api_key", "METAPHOR_API_KEY"
        )
        values["metaphor_api_key"] = metaphor_api_key

        return values

    def results(self, query: str, num_results: int) -> List[Dict]:
        """Run query through Metaphor Search and return metadata.

        Args:
            query: The query to search for.
            num_results: The number of results to return.

        Returns:
            A list of dictionaries with the following keys:
                title - The title of the
                url - The url
                author - Author of the content, if applicable. Otherwise, None.
                date_created - Estimated date created, in YYYY-MM-DD format. Otherwise, None.
        """
        raw_search_results = self._metaphor_search_results(
            query, num_results=num_results)
        cleaned_results = []
        for result in raw_search_results:
            cleaned_results.append(
                {
                    "title": result["title"],
                    "url": result["url"],
                    "author": result["author"],
                    "date_created": result["dateCreated"],
                }
            )

        return cleaned_results
