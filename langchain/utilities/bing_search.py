"""Util that calls Bing Search."""
import requests

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, root_validator

from langchain.utils import get_from_dict_or_env


class BingSearchAPIWrapper(BaseModel):
    """
    Wrapper for Bing Search API.
    """

    search_engine: Any  #: :meta private:
    bing_subscription_key: Optional[str] = None
    bing_search_url: Optional[str] = None

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    def _bing_search_results(self, search_term: str, count: int) -> List[dict]:
        headers = {"Ocp-Apim-Subscription-Key": self.bing_subscription_key}
        params = {"q": search_term, "count": count, "textDecorations": True, "textFormat": "HTML"}
        response = requests.get(self.bing_search_url, headers=headers, params=params)
        response.raise_for_status()
        search_results = response.json()
        return search_results["webPages"]["value"]

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and endpoint exists in environment."""

        bing_subscription_key = get_from_dict_or_env(
            values, "bing_subscription_key", "BING_SUBSCRIPTION_KEY"
        )
        values["bing_subscription_key"] = bing_subscription_key

        bing_search_url = get_from_dict_or_env(
            values, "bing_search_url", "BING_SEARCH_URL"
        )

        values["bing_search_url"] = bing_search_url

        return values

    def run(self, query: str) -> str:
        """Run query through BingSearch and parse result."""
        snippets = []
        results = self._bing_search_results(query, count=10)
        if len(results) == 0:
            return "No good Bing Search Result was found"
        for result in results:
            snippets.append(result["snippet"])

        return " ".join(snippets)