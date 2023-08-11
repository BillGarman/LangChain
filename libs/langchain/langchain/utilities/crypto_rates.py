"""Util that calls AlphaVantage for Currency Exchange Rate."""
from typing import Any, Dict, Optional

import requests
from pydantic import Extra, root_validator

from langchain.tools.base import BaseModel
from langchain.utils import get_from_dict_or_env


class AlphaVantageAPIWrapper(BaseModel):
    """Wrapper for AlphaVantage API for Currency Exchange Rate.

    Docs for using:

    1. Go to AlphaVantage and sign up for an API key
    2. Save your API KEY into ALPHAVANTAGE_API_KEY env variable
    """

    alphavantage_api_key: Optional[str] = None

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    @root_validator(pre=True)
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key exists in environment."""
        alphavantage_api_key = get_from_dict_or_env(
            values, "alphavantage_api_key", "ALPHAVANTAGE_API_KEY"
        )
        values["alphavantage_api_key"] = alphavantage_api_key

        return values

    def _get_exchange_rate(
        self, from_currency: str, to_currency: str
    ) -> Dict[str, Any]:
        """Make a request to the AlphaVantage API to get the exchange rate."""
        base_url = "https://www.alphavantage.co/query/"
        function = "CURRENCY_EXCHANGE_RATE"
        apikey = self.alphavantage_api_key

        response = requests.get(
            base_url,
            params={
                "function": function,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "apikey": apikey,
            },
        )

        response.raise_for_status()
        data = response.json()

        if "Error Message" in data:
            raise ValueError(f"API Error: {data['Error Message']}")

        return data

    def run(self, from_currency: str, to_currency: str) -> str:
        """Get the current exchange rate for a specified currency pair."""
        standard_currencies = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]

        if to_currency not in standard_currencies:
            from_currency, to_currency = to_currency, from_currency

        data = self._get_exchange_rate(from_currency, to_currency)
        return data["Realtime Currency Exchange Rate"]
