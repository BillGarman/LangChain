import json
import urllib.request
import warnings
from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from langchain_core.language_models.llms import BaseLLM
from langchain_core.utils import get_from_dict_or_env
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import Generation, LLMResult
from langchain_core.pydantic_v1 import BaseModel, root_validator, validator


class AzureMLEndpointClient(object):
    """AzureML Managed Endpoint client."""

    def __init__(
        self, endpoint_url: str, endpoint_api_key: str, deployment_name: str = ""
    ) -> None:
        """Initialize the class."""
        if not endpoint_api_key or not endpoint_url:
            raise ValueError(
                """A key/token and REST endpoint should 
                be provided to invoke the endpoint"""
            )
        self.endpoint_url = endpoint_url
        self.endpoint_api_key = endpoint_api_key
        self.deployment_name = deployment_name

    def call(
        self,
        body: bytes,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> bytes:
        """call."""

        # The azureml-model-deployment header will force the request to go to a
        # specific deployment. Remove this header to have the request observe the
        # endpoint traffic rules.
        headers = {
            "Content-Type": "application/json",
            "Authorization": ("Bearer " + self.endpoint_api_key),
        }
        if self.deployment_name != "":
            headers["azureml-model-deployment"] = self.deployment_name

        req = urllib.request.Request(self.endpoint_url, body, headers)
        response = urllib.request.urlopen(req, timeout=kwargs.get("timeout", 50))
        result = response.read()
        return result


class AzureMLEndpointApiType(str, Enum):
    """Azure ML endpoints API types. Use `realtime` for models deployed in hosted
    infrastructure, or `serverless` for models deployed as a service with a
    pay-as-you-go billing or PTU.
    """

    realtime = "realtime"
    serverless = "serverless"


class ContentFormatterBase:
    """Transform request and response of AzureML endpoint to match with
    required schema.
    """

    """
    Example:
        .. code-block:: python
        
            class ContentFormatter(ContentFormatterBase):
                content_type = "application/json"
                accepts = "application/json"
                
                def format_request_payload(
                    self, 
                    prompt: str, 
                    model_kwargs: Dict,
                    api_type: AzureMLEndpointApiType,
                ) -> bytes:
                    input_str = json.dumps(
                        {
                            "inputs": {"input_string": [prompt]}, 
                            "parameters": model_kwargs,
                        }
                    )
                    return str.encode(input_str)
                    
                def format_response_payload(
                        self, output: str, api_type: AzureMLEndpointApiType
                    ) -> str:
                    response_json = json.loads(output)
                    return response_json[0]["0"]
    """
    content_type: Optional[str] = "application/json"
    """The MIME type of the input data passed to the endpoint"""

    accepts: Optional[str] = "application/json"
    """The MIME type of the response data returned from the endpoint"""

    format_error_msg: Optional[
        str
    ] = "Error while formatting response payload for chat model of type `{api_type}`. Are you using the right formatter for the deployed model and endpoint type?"

    @staticmethod
    def escape_special_characters(prompt: str) -> str:
        """Escapes any special characters in `prompt`"""
        escape_map = {
            "\\": "\\\\",
            '"': '\\"',
            "\b": "\\b",
            "\f": "\\f",
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
        }

        # Replace each occurrence of the specified characters with escaped versions
        for escape_sequence, escaped_sequence in escape_map.items():
            prompt = prompt.replace(escape_sequence, escaped_sequence)

        return prompt

    @property
    def supported_api_types(self) -> List[AzureMLEndpointApiType]:
        """Supported APIs for the given formatter. Azure ML supports
        deploying models using different hosting methods. Each method may have
        a different API structure."""

        return [AzureMLEndpointApiType.realtime]

    @abstractmethod
    def format_request_payload(
        self,
        prompt: str,
        model_kwargs: Dict,
        api_type: AzureMLEndpointApiType = AzureMLEndpointApiType.realtime,
    ) -> bytes:
        """Formats the request body according to the input schema of
        the model. Returns bytes or seekable file like object in the
        format specified in the content_type request header.
        """

    @abstractmethod
    def format_response_payload(
        self,
        output: bytes,
        api_type: AzureMLEndpointApiType = AzureMLEndpointApiType.realtime,
    ) -> Generation:
        """Formats the response body according to the output
        schema of the model. Returns the data type that is
        received from the response.
        """


class GPT2ContentFormatter(ContentFormatterBase):
    """Content handler for GPT2"""

    @property
    def supported_api_types(self) -> List[AzureMLEndpointApiType]:
        return [AzureMLEndpointApiType.realtime]

    def format_request_payload(
        self, prompt: str, model_kwargs: Dict, api_type: AzureMLEndpointApiType
    ) -> bytes:
        prompt = ContentFormatterBase.escape_special_characters(prompt)
        request_payload = json.dumps(
            {"inputs": {"input_string": [f'"{prompt}"']}, "parameters": model_kwargs}
        )
        return str.encode(request_payload)

    def format_response_payload(
        self, output: bytes, api_type: AzureMLEndpointApiType
    ) -> Generation:
        try:
            choice = json.loads(output)[0]["0"]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(self.format_error_msg.format(api_type=api_type)) from e
        return Generation(text=choice)


class OSSContentFormatter(GPT2ContentFormatter):
    """Deprecated: Kept for backwards compatibility

    Content handler for LLMs from the OSS catalog."""

    content_formatter: Any = None

    def __init__(self) -> None:
        super().__init__()
        warnings.warn(
            """`OSSContentFormatter` will be deprecated in the future. 
                      Please use `GPT2ContentFormatter` instead.  
                      """
        )


class HFContentFormatter(ContentFormatterBase):
    """Content handler for LLMs from the HuggingFace catalog."""

    @property
    def supported_api_types(self) -> List[AzureMLEndpointApiType]:
        return [AzureMLEndpointApiType.realtime]

    def format_request_payload(
        self, prompt: str, model_kwargs: Dict, api_type: AzureMLEndpointApiType
    ) -> bytes:
        ContentFormatterBase.escape_special_characters(prompt)
        request_payload = json.dumps(
            {"inputs": [f'"{prompt}"'], "parameters": model_kwargs}
        )
        return str.encode(request_payload)

    def format_response_payload(
        self, output: bytes, api_type: AzureMLEndpointApiType
    ) -> Generation:
        try:
            choice = json.loads(output)[0]["0"]["generated_text"]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(self.format_error_msg.format(api_type=api_type)) from e
        return Generation(text=choice)


class DollyContentFormatter(ContentFormatterBase):
    """Content handler for the Dolly-v2-12b model"""

    @property
    def supported_api_types(self) -> List[AzureMLEndpointApiType]:
        return [AzureMLEndpointApiType.realtime]

    def format_request_payload(
        self, prompt: str, model_kwargs: Dict, api_type: AzureMLEndpointApiType
    ) -> bytes:
        prompt = ContentFormatterBase.escape_special_characters(prompt)
        request_payload = json.dumps(
            {
                "input_data": {"input_string": [f'"{prompt}"']},
                "parameters": model_kwargs,
            }
        )
        return str.encode(request_payload)

    def format_response_payload(
        self, output: bytes, api_type: AzureMLEndpointApiType
    ) -> Generation:
        try:
            choice = json.loads(output)[0]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(self.format_error_msg.format(api_type=api_type)) from e
        return Generation(text=choice)


class LlamaContentFormatter(ContentFormatterBase):
    """Content formatter for LLaMa"""

    @property
    def supported_api_types(self) -> List[AzureMLEndpointApiType]:
        return [AzureMLEndpointApiType.realtime, AzureMLEndpointApiType.serverless]

    def format_request_payload(
        self, prompt: str, model_kwargs: Dict, api_type: AzureMLEndpointApiType
    ) -> bytes:
        """Formats the request according to the chosen api"""
        prompt = ContentFormatterBase.escape_special_characters(prompt)
        if api_type == AzureMLEndpointApiType.realtime:
            request_payload = json.dumps(
                {
                    "input_data": {
                        "input_string": [f'"{prompt}"'],
                        "parameters": model_kwargs,
                    }
                }
            )
        elif api_type == AzureMLEndpointApiType.serverless:
            request_payload = json.dumps({"prompt": prompt, **model_kwargs})
        else:
            raise ValueError(
                f"`api_type` {api_type} is not supported by this formatter"
            )
        return str.encode(request_payload)

    def format_response_payload(
        self, output: bytes, api_type: AzureMLEndpointApiType
    ) -> Generation:
        """Formats response"""
        if api_type == AzureMLEndpointApiType.realtime:
            try:
                choice = json.loads(output)[0]["0"]
            except (KeyError, IndexError, TypeError) as e:
                raise ValueError(self.format_error_msg.format(api_type=api_type)) from e
            return Generation(text=choice)
        if api_type == AzureMLEndpointApiType.serverless:
            try:
                choice = json.loads(output)["choices"][0]
                if not isinstance(choice, dict):
                    raise TypeError(
                        f"Endpoint response is not well formed for a chat model. Expected `dict` but `{type(choice)}` was received."
                    )
            except (KeyError, IndexError, TypeError) as e:
                raise ValueError(self.format_error_msg.format(api_type=api_type)) from e
            return Generation(
                text=choice["text"].strip(),
                generation_info=dict(
                    finish_reason=choice.get("finish_reason"),
                    logprobs=choice.get("logprobs"),
                ),
            )
        raise ValueError(f"`api_type` {api_type} is not supported by this formatter")


class AzureMLBaseEndpoint(BaseModel):
    """Azure ML Online Endpoint models."""

    endpoint_url: str = ""
    """URL of pre-existing Endpoint. Should be passed to constructor or specified as 
        env var `AZUREML_ENDPOINT_URL`."""

    endpoint_api_type: AzureMLEndpointApiType = AzureMLEndpointApiType.realtime
    """Type of the endpoint being consumed. Possible values are `serverless` for 
        pay-as-you-go and `realtime` for real-time endpoints. """

    endpoint_api_key: str = ""
    """Authentication Key for Endpoint. Should be passed to constructor or specified as
        env var `AZUREML_ENDPOINT_API_KEY`."""

    deployment_name: str = ""
    """Deployment Name for Endpoint. NOT REQUIRED to call endpoint. Should be passed 
        to constructor or specified as env var `AZUREML_DEPLOYMENT_NAME`."""

    http_client: Any = None  #: :meta private:

    content_formatter: Any = None
    """The content formatter that provides an input and output
    transform function to handle formats between the LLM and
    the endpoint"""

    model_kwargs: Optional[dict] = None
    """Keyword arguments to pass to the model."""

    @root_validator()
    @classmethod
    def validate_endpoint_api_type(cls, values: Dict) -> Dict:
        content_formatter = values.get("content_formatter")
        endpoint_api_type, endpoint_url = (
            values.get("endpoint_api_type"),
            values.get("endpoint_url"),
        )
        if endpoint_url.endswith("/"):
            endpoint_url = endpoint_url[:-1]
        if endpoint_url.endswith("inference.ml.azure.com"):
            raise ValueError(
                "`endpoint_url` should contain the full invocation URL including "
                "`/score` for `endpoint_api_type='realtime'` or `/v1/completions` "
                "or `/v1/chat/completions` for `endpoint_api_type='serverless'`"
            )
        if (
            endpoint_api_type == AzureMLEndpointApiType.realtime
            and not endpoint_url.endswith("/score")
        ):
            raise ValueError(
                "Endpoints of type `realtime` should follow the format "
                "`https://<your-endpoint>.<your_region>.inference.ml.azure.com/score`."
                " If your endpoint URL ends with `/v1/completions` or"
                "`/v1/chat/completions`, use `endpoint_api_type='serverless'` instead."
            )
        if endpoint_api_type == AzureMLEndpointApiType.serverless and not (
            endpoint_url.endswith("/v1/completions")
            or endpoint_url.endswith("/v1/chat/completions")
        ):
            raise ValueError(
                "Endpoints of type `serverless` should follow the format "
                "`https://<your-endpoint>.<your_region>.inference.ml.azure.com/v1/chat/completions`"
                " or `https://<your-endpoint>.<your_region>.inference.ml.azure.com/v1/chat/completions`"
            )

        if endpoint_api_type not in content_formatter.supported_api_types:
            raise ValueError(
                f"Content formatter f{type(content_formatter)} is not supported by "
                "this endpoint type."
            )
        return values

    @validator("http_client", always=True, allow_reuse=True)
    @classmethod
    def validate_client(cls, field_value: Any, values: Dict) -> AzureMLEndpointClient:
        """Validate that api key and python package exists in environment."""
        endpoint_key = get_from_dict_or_env(
            values, "endpoint_api_key", "AZUREML_ENDPOINT_API_KEY"
        )
        endpoint_url = get_from_dict_or_env(
            values, "endpoint_url", "AZUREML_ENDPOINT_URL"
        )
        deployment_name = get_from_dict_or_env(
            values, "deployment_name", "AZUREML_DEPLOYMENT_NAME", ""
        )
        http_client = AzureMLEndpointClient(endpoint_url, endpoint_key, deployment_name)
        return http_client


class AzureMLOnlineEndpoint(BaseLLM, AzureMLBaseEndpoint):
    """Azure ML Online Endpoint models.

    Example:
        .. code-block:: python
            azure_llm = AzureMLOnlineEndpoint(
                endpoint_url="https://<your-endpoint>.<your_region>.inference.ml.azure.com/score",
                endpoint_api_type=AzureMLApiType.realtime,
                endpoint_api_key="my-api-key",
                content_formatter=content_formatter,
            )
    """  # noqa: E501

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        _model_kwargs = self.model_kwargs or {}
        return {
            **{"deployment_name": self.deployment_name},
            **{"model_kwargs": _model_kwargs},
        }

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "azureml_endpoint"

    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """Run the LLM on the given prompts.

        Args:
            prompts: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.
        Returns:
            The string generated by the model.
        Example:
            .. code-block:: python
                response = azureml_model("Tell me a joke.")
        """
        _model_kwargs = self.model_kwargs or {}
        _model_kwargs.update(kwargs)
        if stop:
            _model_kwargs["stop"] = stop
        generations = []

        for prompt in prompts:
            request_payload = self.content_formatter.format_request_payload(
                prompt, _model_kwargs, self.endpoint_api_type
            )
            response_payload = self.http_client.call(
                body=request_payload, run_manager=run_manager
            )
            generated_text = self.content_formatter.format_response_payload(
                response_payload, self.endpoint_api_type
            )
            generations.append([generated_text])

        return LLMResult(generations=generations)
