from __future__ import annotations

import json
import warnings
from abc import ABC
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Mapping, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM
from langchain_core.outputs import Generation, GenerationChunk, LLMResult
from langchain_core.pydantic_v1 import BaseModel, Extra, Field, root_validator
from langchain_core.utils import get_from_dict_or_env

from langchain_community.llms.utils import enforce_stop_tokens
from langchain_community.utilities.anthropic import (
    get_num_tokens_anthropic,
    get_token_ids_anthropic,
)

if TYPE_CHECKING:
    from botocore.config import Config

GUARDRAILS_BODY_KEY = "amazon-bedrock-guardrailAssessment"
HUMAN_PROMPT = "\n\nHuman:"
ASSISTANT_PROMPT = "\n\nAssistant:"
ALTERNATION_ERROR = (
    "Error: Prompt must alternate between '\n\nHuman:' and '\n\nAssistant:'."
)


def _add_newlines_before_ha(input_text: str) -> str:
    new_text = input_text
    for word in ["Human:", "Assistant:"]:
        new_text = new_text.replace(word, "\n\n" + word)
        for i in range(2):
            new_text = new_text.replace("\n\n\n" + word, "\n\n" + word)
    return new_text


def _human_assistant_format(input_text: str) -> str:
    if input_text.count("Human:") == 0 or (
        input_text.find("Human:") > input_text.find("Assistant:")
        and "Assistant:" in input_text
    ):
        input_text = HUMAN_PROMPT + " " + input_text  # SILENT CORRECTION
    if input_text.count("Assistant:") == 0:
        input_text = input_text + ASSISTANT_PROMPT  # SILENT CORRECTION
    if input_text[: len("Human:")] == "Human:":
        input_text = "\n\n" + input_text
    input_text = _add_newlines_before_ha(input_text)
    count = 0
    # track alternation
    for i in range(len(input_text)):
        if input_text[i : i + len(HUMAN_PROMPT)] == HUMAN_PROMPT:
            if count % 2 == 0:
                count += 1
            else:
                warnings.warn(ALTERNATION_ERROR + f" Received {input_text}")
        if input_text[i : i + len(ASSISTANT_PROMPT)] == ASSISTANT_PROMPT:
            if count % 2 == 1:
                count += 1
            else:
                warnings.warn(ALTERNATION_ERROR + f" Received {input_text}")

    if count % 2 == 1:  # Only saw Human, no Assistant
        input_text = input_text + ASSISTANT_PROMPT  # SILENT CORRECTION

    return input_text


class LLMInputOutputAdapter:
    """Adapter class to prepare the inputs from Langchain to a format
    that LLM model expects.

    It also provides helper function to extract
    the generated text from the model response."""

    provider_to_output_key_map = {
        "anthropic": "completion",
        "amazon": "outputText",
        "cohere": "text",
        "meta": "generation",
    }

    @classmethod
    def prepare_input(
        cls, provider: str, prompt: str, model_kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        input_body = {**model_kwargs}
        if provider == "anthropic":
            input_body["prompt"] = _human_assistant_format(prompt)
        elif provider in ("ai21", "cohere", "meta"):
            input_body["prompt"] = prompt
        elif provider == "amazon":
            input_body = dict()
            input_body["inputText"] = prompt
            input_body["textGenerationConfig"] = {**model_kwargs}
        else:
            input_body["inputText"] = prompt

        if provider == "anthropic" and "max_tokens_to_sample" not in input_body:
            input_body["max_tokens_to_sample"] = 256

        return input_body

    @classmethod
    def prepare_output(cls, provider: str, response: Any) -> dict:
        if provider == "anthropic":
            response_body = json.loads(response.get("body").read().decode())
            text = response_body.get("completion")
        else:
            response_body = json.loads(response.get("body").read())

            if provider == "ai21":
                text = response_body.get("completions")[0].get("data").get("text")
            elif provider == "cohere":
                text = response_body.get("generations")[0].get("text")
            elif provider == "meta":
                text = response_body.get("generation")
            else:
                text = response_body.get("results")[0].get("outputText")

        return {
            "text" : text,
            "body" : response_body,
        }


    @classmethod
    def prepare_output_stream(
        cls, provider: str, response: Any, stop: Optional[List[str]] = None
    ) -> Iterator[GenerationChunk]:
        stream = response.get("body")

        if not stream:
            return

        if provider not in cls.provider_to_output_key_map:
            raise ValueError(
                f"Unknown streaming response output key for provider: {provider}"
            )

        for event in stream:
            chunk = event.get("chunk")
            if chunk:
                chunk_obj = json.loads(chunk.get("bytes").decode())
                if provider == "cohere" and (
                    chunk_obj["is_finished"]
                    or chunk_obj[cls.provider_to_output_key_map[provider]]
                    == "<EOS_TOKEN>"
                ):
                    return

                # chunk obj format varies with provider
                yield GenerationChunk(
                    text=chunk_obj[cls.provider_to_output_key_map[provider]],
                    generation_info={
                        GUARDRAILS_BODY_KEY : chunk_obj.get(GUARDRAILS_BODY_KEY) if GUARDRAILS_BODY_KEY in chunk_obj else None,
                    }
                )


class BedrockBase(BaseModel, ABC):
    """Base class for Bedrock models."""

    client: Any = Field(exclude=True)  #: :meta private:

    region_name: Optional[str] = None
    """The aws region e.g., `us-west-2`. Fallsback to AWS_DEFAULT_REGION env variable
    or region specified in ~/.aws/config in case it is not provided here.
    """

    credentials_profile_name: Optional[str] = Field(default=None, exclude=True)
    """The name of the profile in the ~/.aws/credentials or ~/.aws/config files, which
    has either access keys or role information specified.
    If not specified, the default credential profile or, if on an EC2 instance,
    credentials from IMDS will be used.
    See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
    """

    config: Optional[Config] = None
    """An optional botocore.config.Config instance to pass to the client."""

    model_id: str
    """Id of the model to call, e.g., amazon.titan-text-express-v1, this is
    equivalent to the modelId property in the list-foundation-models api"""

    model_kwargs: Optional[Dict] = None
    """Keyword arguments to pass to the model."""

    endpoint_url: Optional[str] = None
    """Needed if you don't want to default to us-east-1 endpoint"""

    streaming: bool = False
    """Whether to stream the results."""

    provider_stop_sequence_key_name_map: Mapping[str, str] = {
        "anthropic": "stop_sequences",
        "amazon": "stopSequences",
        "ai21": "stop_sequences",
        "cohere": "stop_sequences",
    }

    guardrails: Optional[Mapping[str, str]] = {
        "id" : None,
        "version" : None,
        "trace" : False
    }
    """
    An optional dictionary to configure guardrails for Bedrock.

    This field 'guardrails' consists of two keys: 'id' and 'version',
    which should be strings, but are initialized to None. It's used to
    determine if specific guardrails are enabled and properly set.

    Type:
        Optional[Mapping[str, str]]: A mapping with 'id' and 'version' keys.

    Example:
    llm = Bedrock(model_id="<model_id>", client=<bedrock_client>,
                  model_kwargs={},
                  guardrails={
                        "id": "<guardrail_id>",
                        "version": "<guardrail_version>"})
    """

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that AWS credentials to and python package exists in environment."""

        # Skip creating new client if passed in constructor
        if values["client"] is not None:
            return values

        try:
            import boto3

            if values["credentials_profile_name"] is not None:
                session = boto3.Session(profile_name=values["credentials_profile_name"])
            else:
                # use default credentials
                session = boto3.Session()

            values["region_name"] = get_from_dict_or_env(
                values,
                "region_name",
                "AWS_DEFAULT_REGION",
                default=session.region_name,
            )

            client_params = {}
            if values["region_name"]:
                client_params["region_name"] = values["region_name"]
            if values["endpoint_url"]:
                client_params["endpoint_url"] = values["endpoint_url"]
            if values["config"]:
                client_params["config"] = values["config"]

            values["client"] = session.client("bedrock-runtime", **client_params)

        except ImportError:
            raise ModuleNotFoundError(
                "Could not import boto3 python package. "
                "Please install it with `pip install boto3`."
            )
        except Exception as e:
            raise ValueError(
                "Could not load credentials to authenticate with AWS client. "
                "Please check that credentials in the specified "
                "profile name are valid."
            ) from e

        return values

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        _model_kwargs = self.model_kwargs or {}
        return {
            **{"model_kwargs": _model_kwargs},
        }

    def _get_provider(self) -> str:
        return self.model_id.split(".")[0]

    @property
    def _model_is_anthropic(self) -> bool:
        return self._get_provider() == "anthropic"

    @property
    def _guardrails_enabled(self) -> bool:
        """
        Determines if guardrails are enabled and correctly configured.
        Checks if 'guardrails' is a dictionary with non-empty 'id' and 'version' keys.
        Checks if 'guardrails.trace' is true.

        Returns:
            bool: True if guardrails are correctly configured, False otherwise.
        Raises:
            TypeError: If 'guardrails' lacks 'id' or 'version' keys.
        """
        try:

            return isinstance(self.guardrails, dict) and bool(self.guardrails["id"]) and bool(self.guardrails["version"])

        except KeyError as e:
            raise TypeError(f"Guardrails must be a dictionary with 'id' and 'version' keys.") from e


    def _get_guardrails_canonical_form(self) -> Dict[str, Any]:
        """
            The canonical way to pass in guardrails to the bedrock service
            adheres to the following format:

            "amazon-bedrock-guardrailDetails": {
                "guardrailId": "string",
                "guardrailVersion": "string"
            }
        """
        return {
            "amazon-bedrock-guardrailDetails" : {
                "guardrailId": self.guardrails.get("id"),
                "guardrailVersion": self.guardrails.get("version"),
            }}


    def _prepare_input_and_invoke(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        _model_kwargs = self.model_kwargs or {}
        provider = self._get_provider()
        params = {**_model_kwargs, **kwargs}
        if self._guardrails_enabled:
            params.update(self._get_guardrails_canonical_form())
        input_body = LLMInputOutputAdapter.prepare_input(provider, prompt, params)
        body = json.dumps(input_body)
        accept = "application/json"
        contentType = "application/json"

        request_options = {
            "body": body,
            "modelId": self.model_id,
            "accept": accept,
            "contentType": contentType
        }

        if self._guardrails_enabled:
            request_options["guardrail"] = "ENABLED"
            if self.guardrails.get("trace"):
                request_options["trace"] = "ENABLED"

        try:
            response = self.client.invoke_model(**request_options)

            text, body = LLMInputOutputAdapter.prepare_output(provider, response).values()

        except Exception as e:
            raise ValueError(f"Error raised by bedrock service: {e}")

        if stop is not None:
            text = enforce_stop_tokens(text, stop)

        # verify and raise callback error if any middleware intervened
        error, reason = self._inspect_bedrock_services_signal(body, run_manager).values()

        if error and run_manager is not None:
            run_manager.on_llm_error(error, reason=reason)

        return text


    def _inspect_bedrock_services_signal(self, body: dict) -> dict:
        """
            This function checks the response body for an interrupt flag or message that indicates
            whether any of the Bedrock services have intervened in the processing flow. It is
            primarily used to identify modifications or interruptions imposed by these services
            during the request-response cycle with a Large Language Model (LLM).
            """

        if self._guardrails_enabled and self.guardrails.get("trace"):
            if self._check_if_guardrails_intervened(body):
                return {
                    "error" : True,
                    "reason" : "GUARDRAIL_INTERVENED"
                }

        return {
            "error" : False,
        }

    def _check_if_guardrails_intervened(self, body: dict) -> bool:
        """
        Determines if guardrails for Bedrock service intervened in the generation of response.

        Args:
           body dict():

        Returns:
           str: The text that was generated by the model.
        """

        if body.get(GUARDRAILS_BODY_KEY) == "GUARDRAIL_INTERVENED":
            return True

        return False

    def _prepare_input_and_invoke_stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        _model_kwargs = self.model_kwargs or {}
        provider = self._get_provider()

        if stop:
            if provider not in self.provider_stop_sequence_key_name_map:
                raise ValueError(
                    f"Stop sequence key name for {provider} is not supported."
                )

            # stop sequence from _generate() overrides
            # stop sequences in the class attribute
            _model_kwargs[self.provider_stop_sequence_key_name_map.get(provider)] = stop

        if provider == "cohere":
            _model_kwargs["stream"] = True

        params = {**_model_kwargs, **kwargs}

        if self._guardrails_enabled:
            params.update(self._get_guardrails_canonical_form())

        input_body = LLMInputOutputAdapter.prepare_input(provider, prompt, params)
        body = json.dumps(input_body)


        request_options = {
            "body": body,
            "modelId": self.model_id,
            "accept": "application/json",
            "contentType": "application/json"
        }

        if self._guardrails_enabled:
            request_options["guardrail"] = "ENABLED"


        try:
            response = self.client.invoke_model_with_response_stream(**request_options)

        except Exception as e:
            raise ValueError(f"Error raised by bedrock service: {e}")

        for chunk in LLMInputOutputAdapter.prepare_output_stream(
            provider, response, stop
        ):

            yield chunk

            # Verify and raise a callback error if any intervention occurs or signal sent from a Bedrock service, such as when guardrails are triggered.
            result = self._inspect_bedrock_services_signal(chunk.generation_info)

            if run_manager is not None:
                run_manager.on_llm_new_token(chunk.text, chunk=chunk)

                if result.get("error"):
                    run_manager.on_llm_error(result.get("error"), reason=result.get("reason"))



class Bedrock(LLM, BedrockBase):
    """Bedrock models.

    To authenticate, the AWS client uses the following methods to
    automatically load credentials:
    https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html

    If a specific credential profile should be used, you must pass
    the name of the profile from the ~/.aws/credentials file that is to be used.

    Make sure the credentials / roles used have the required policies to
    access the Bedrock service.
    """

    """
    Example:
        .. code-block:: python

            from bedrock_langchain.bedrock_llm import BedrockLLM

            llm = BedrockLLM(
                credentials_profile_name="default",
                model_id="amazon.titan-text-express-v1",
                streaming=True
            )

    """

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "amazon_bedrock"

    @classmethod
    def is_lc_serializable(cls) -> bool:
        """Return whether this model can be serialized by Langchain."""
        return True

    @classmethod
    def get_lc_namespace(cls) -> List[str]:
        """Get the namespace of the langchain object."""
        return ["langchain", "llms", "bedrock"]

    @property
    def lc_attributes(self) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {}

        if self.region_name:
            attributes["region_name"] = self.region_name

        return attributes

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """Call out to Bedrock service with streaming.

        Args:
            prompt (str): The prompt to pass into the model
            stop (Optional[List[str]], optional): Stop sequences. These will
                override any stop sequences in the `model_kwargs` attribute.
                Defaults to None.
            run_manager (Optional[CallbackManagerForLLMRun], optional): Callback
                run managers used to process the output. Defaults to None.

        Returns:
            Iterator[GenerationChunk]: Generator that yields the streamed responses.

        Yields:
            Iterator[GenerationChunk]: Responses from the model.
        """
        return self._prepare_input_and_invoke_stream(
            prompt=prompt, stop=stop, run_manager=run_manager, **kwargs
        )

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call out to Bedrock service model.

        Args:
            prompt: The prompt to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            The string generated by the model.

        Example:
            .. code-block:: python

                response = llm("Tell me a joke.")
        """

        if self.streaming:
            completion = ""
            for chunk in self._stream(
                prompt=prompt, stop=stop, run_manager=run_manager, **kwargs
            ):
                completion += chunk.text
            return completion

        return self._prepare_input_and_invoke(prompt=prompt, stop=stop,run_manager=run_manager, **kwargs)

    def get_num_tokens(self, text: str) -> int:
        if self._model_is_anthropic:
            return get_num_tokens_anthropic(text)
        else:
            return super().get_num_tokens(text)

    def get_token_ids(self, text: str) -> List[int]:
        if self._model_is_anthropic:
            return get_token_ids_anthropic(text)
        else:
            return super().get_token_ids(text)
