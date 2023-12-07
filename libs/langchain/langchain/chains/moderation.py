from typing import Dict, List, Optional

import openai
from openai.types import ModerationCreateResponse, Moderation
from openai.resources.moderations import Moderations

from langchain_core.pydantic_v1 import root_validator
from langchain.callbacks.manager import CallbackManagerForChainRun
from langchain.utils import get_from_dict_or_env
from langchain.chains.base import Chain


class OpenAIModerationChain(Chain):
    """Pass input through a moderation endpoint.

    To use, you should have the ``openai`` python package installed, and the
    environment variable ``OPENAI_API_KEY`` set with your API key.

    Any parameters that are valid to be passed to the openai.create call can be passed
    in, even if not explicitly saved on this class.

    Example:
        .. code-block:: python

            from langchain.chains import OpenAIModerationChain
            moderation = OpenAIModerationChain()
    """

    client: Moderations = openai.moderations  #: :meta private:
    model_name: Optional[str] = None
    """Moderation model name to use."""
    error: bool = False
    """Whether or not to error if bad content was found."""
    input_key: str = "input"  #: :meta private:
    output_key: str = "output"  #: :meta private:
    openai_api_key: Optional[str] = None
    openai_organization: Optional[str] = None

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        openai_api_key = get_from_dict_or_env(
            values, "openai_api_key", "OPENAI_API_KEY"
        )
        openai_organization = get_from_dict_or_env(
            values,
            "openai_organization",
            "OPENAI_ORGANIZATION",
            default="",
        )
        try:
            openai.api_key = openai_api_key
            if openai_organization:
                openai.organization = openai_organization
            values["client"] = openai.moderations
        except ImportError:
            raise ImportError(
                "Could not import openai python package. "
                "Please install it with `pip install openai`."
            )
        return values

    @property
    def input_keys(self) -> List[str]:
        """Expect input key.

        :meta private:
        """
        return [self.input_key]

    @property
    def output_keys(self) -> List[str]:
        """Return output key.

        :meta private:
        """
        return [self.output_key]

    def _moderate(self, text: str, results: Moderation) -> str:
        if results.flagged:
            error_str = "Text was found that violates OpenAI's content policy."
            if self.error:
                raise ValueError(error_str)
            else:
                return error_str
        return text

    def _call(
        self,
        inputs: Dict[str, str],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        text: str = inputs[self.input_key]
        results: ModerationCreateResponse = self.client.create(input=text)
        output: str = self._moderate(text, results.results[0])
        return {self.output_key: output}