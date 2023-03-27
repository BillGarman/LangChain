"""Wrapper around Modal API."""
import logging
from typing import Any, Dict, List, Mapping, Optional

import requests
from pydantic import BaseModel, Extra, Field, root_validator

from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens

logger = logging.getLogger(__name__)


class Modal(LLM, BaseModel):
    """Wrapper around Modal large language models.

    To use, you should have the ``modal-client`` python package installed.

    Any parameters that are valid to be passed to the call can be passed
    in, even if not explicitly saved on this class.

    Example:
        .. code-block:: python
            from langchain.llms import Modal
            endpoint_url = "..."
            modal = Modal(model_id=endpoint_url)

    """

    id = "modal"
    """Unique ID for this provider class."""

    model_id: str
    """
    Model ID to invoke by this provider via generate/agenerate.
    For Modal, this is the endpoint URL.
    """

    models = ["*"]
    """List of supported models by their IDs. For registry providers, this will
    be just ["*"]."""

    pypi_package_deps = ["modal-client"]
    """List of PyPi package dependencies."""

    auth_strategy = None
    """Authentication/authorization strategy. Declares what credentials are
    required to use this model provider. Generally should not be `None`."""

    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Holds any model parameters valid for `create` call not
    explicitly specified."""

    class Config:
        """Configuration for this pydantic config."""

        extra = Extra.forbid

    @root_validator(pre=True)
    def build_extra(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Build extra kwargs from additional params that were passed in."""
        all_required_field_names = {field.alias for field in cls.__fields__.values()}

        extra = values.get("model_kwargs", {})
        for field_name in list(values):
            if field_name not in all_required_field_names:
                if field_name in extra:
                    raise ValueError(f"Found {field_name} supplied twice.")
                logger.warning(
                    f"""{field_name} was transfered to model_kwargs.
                    Please confirm that {field_name} is what you intended."""
                )
                extra[field_name] = values.pop(field_name)
        values["model_kwargs"] = extra
        return values

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            **{"model_id": self.model_id},
            **{"model_kwargs": self.model_kwargs},
        }

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Call to Modal endpoint."""
        params = self.model_kwargs or {}
        response = requests.post(
            url=self.model_id,
            headers={
                "Content-Type": "application/json",
            },
            json={"prompt": prompt, **params},
        )
        try:
            if prompt in response.json()["prompt"]:
                response_json = response.json()
        except KeyError:
            raise ValueError("LangChain requires 'prompt' key in response.")
        text = response_json["prompt"]
        if stop is not None:
            # I believe this is required since the stop tokens
            # are not enforced by the model parameters
            text = enforce_stop_tokens(text, stop)
        return text
