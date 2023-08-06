from __future__ import annotations

import logging
import warnings
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import numpy as np
from pydantic import BaseModel, Extra, Field, root_validator
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from langchain.embeddings.base import Embeddings
from langchain.utils import get_from_dict_or_env, get_pydantic_field_names

logger = logging.getLogger(__name__)


def _create_retry_decorator(embeddings: OpenAIEmbeddings) -> Callable[[Any], Any]:
    import openai

    min_seconds = 4
    max_seconds = 10
    # Wait 2^x * 1 second between each retry starting with
    # 4 seconds, then up to 10 seconds, then 10 seconds afterwards
    return retry(
        reraise=True,
        stop=stop_after_attempt(embeddings.max_retries),
        wait=wait_exponential(multiplier=1, min=min_seconds, max=max_seconds),
        retry=(
            retry_if_exception_type(openai.error.Timeout)
            | retry_if_exception_type(openai.error.APIError)
            | retry_if_exception_type(openai.error.APIConnectionError)
            | retry_if_exception_type(openai.error.RateLimitError)
            | retry_if_exception_type(openai.error.ServiceUnavailableError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


def _async_retry_decorator(embeddings: OpenAIEmbeddings) -> Any:
    import openai

    min_seconds = 4
    max_seconds = 10
    # Wait 2^x * 1 second between each retry starting with
    # 4 seconds, then up to 10 seconds, then 10 seconds afterwards
    async_retrying = AsyncRetrying(
        reraise=True,
        stop=stop_after_attempt(embeddings.max_retries),
        wait=wait_exponential(multiplier=1, min=min_seconds, max=max_seconds),
        retry=(
            retry_if_exception_type(openai.error.Timeout)
            | retry_if_exception_type(openai.error.APIError)
            | retry_if_exception_type(openai.error.APIConnectionError)
            | retry_if_exception_type(openai.error.RateLimitError)
            | retry_if_exception_type(openai.error.ServiceUnavailableError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )

    def wrap(func: Callable) -> Callable:
        async def wrapped_f(*args: Any, **kwargs: Any) -> Callable:
            async for _ in async_retrying:
                return await func(*args, **kwargs)
            raise AssertionError("this is unreachable")

        return wrapped_f

    return wrap


# https://stackoverflow.com/questions/76469415/getting-embeddings-of-length-1-from-langchain-openaiembeddings
def _check_response(response: dict) -> dict:
    if any(len(d["embedding"]) == 1 for d in response["data"]):
        import openai

        raise openai.error.APIError("OpenAI API returned an empty embedding")
    return response


def embed_with_retry(embeddings: OpenAIEmbeddings, **kwargs: Any) -> Any:
    """Use tenacity to retry the embedding call."""
    retry_decorator = _create_retry_decorator(embeddings)

    @retry_decorator
    def _embed_with_retry(**kwargs: Any) -> Any:
        response = embeddings.client.create(**kwargs)
        return _check_response(response)

    return _embed_with_retry(**kwargs)


async def async_embed_with_retry(embeddings: OpenAIEmbeddings, **kwargs: Any) -> Any:
    """Use tenacity to retry the embedding call."""

    @_async_retry_decorator(embeddings)
    async def _async_embed_with_retry(**kwargs: Any) -> Any:
        response = await embeddings.client.acreate(**kwargs)
        return _check_response(response)

    return await _async_embed_with_retry(**kwargs)


class OpenAIEmbeddings(BaseModel, Embeddings):
    """OpenAI embedding models.

    To use, you should have the ``openai`` python package installed, and the
    environment variable ``OPENAI_API_KEY`` set with your API key or pass it
    as a named parameter to the constructor.

    Example:
        .. code-block:: python

            from langchain.embeddings import OpenAIEmbeddings
            openai = OpenAIEmbeddings(openai_api_key="my-api-key")

    In order to use the library with Microsoft Azure endpoints, you need to set
    the OPENAI_API_TYPE, OPENAI_API_BASE, OPENAI_API_KEY and OPENAI_API_VERSION.
    The OPENAI_API_TYPE must be set to 'azure' and the others correspond to
    the properties of your endpoint.
    In addition, the deployment name must be passed as the model parameter.

    Example:
        .. code-block:: python

            import os
            os.environ["OPENAI_API_TYPE"] = "azure"
            os.environ["OPENAI_API_BASE"] = "https://<your-endpoint.openai.azure.com/"
            os.environ["OPENAI_API_KEY"] = "your AzureOpenAI key"
            os.environ["OPENAI_API_VERSION"] = "2023-05-15"
            os.environ["OPENAI_PROXY"] = "http://your-corporate-proxy:8080"

            from langchain.embeddings.openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(
                deployment="your-embeddings-deployment-name",
                model="your-embeddings-model-name",
                openai_api_base="https://your-endpoint.openai.azure.com/",
                openai_api_type="azure",
            )
            text = "This is a test query."
            query_result = embeddings.embed_query(text)

    """

    client: Any  #: :meta private:
    model: str = "text-embedding-ada-002"
    deployment: str = model  # to support Azure OpenAI Service custom deployment names
    openai_api_version: Optional[str] = None
    # to support Azure OpenAI Service custom endpoints
    openai_api_base: Optional[str] = None
    # to support Azure OpenAI Service custom endpoints
    openai_api_type: Optional[str] = None
    # to support explicit proxy for OpenAI
    openai_proxy: Optional[str] = None
    embedding_ctx_length: Optional[int] = 8191
    """The maximum number of tokens to embed at once."""
    openai_api_key: Optional[str] = None
    openai_organization: Optional[str] = None
    allowed_special: Union[Literal["all"], Set[str]] = set()
    disallowed_special: Union[Literal["all"], Set[str], Sequence[str]] = "all"
    chunk_size: int = 1000
    """Maximum number of texts to embed in each batch"""
    max_retries: int = 6
    """Maximum number of retries to make when generating."""
    request_timeout: Optional[Union[float, Tuple[float, float]]] = None
    """Timeout in seconds for the OpenAPI request."""
    headers: Any = None
    tiktoken_model_name: Optional[str] = None
    """The model name to pass to tiktoken when using this class. 
    Tiktoken is used to count the number of tokens in documents to constrain 
    them to be under a certain limit. By default, when set to None, this will 
    be the same as the embedding model name. However, there are some cases 
    where you may want to use this Embedding class with a model name not 
    supported by tiktoken. This can include when using Azure embeddings or 
    when using one of the many model providers that expose an OpenAI-like 
    API but with different models. In those cases, in order to avoid erroring 
    when tiktoken is called, you can specify a model name to use here."""
    show_progress_bar: bool = False
    """Whether to show a progress bar when embedding."""
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Holds any model parameters valid for `create` call not explicitly specified."""

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    @root_validator(pre=True)
    def build_extra(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Build extra kwargs from additional params that were passed in."""
        all_required_field_names = get_pydantic_field_names(cls)
        extra = values.get("model_kwargs", {})
        for field_name in list(values):
            if field_name in extra:
                raise ValueError(f"Found {field_name} supplied twice.")
            if field_name not in all_required_field_names:
                warnings.warn(
                    f"""WARNING! {field_name} is not default parameter.
                    {field_name} was transferred to model_kwargs.
                    Please confirm that {field_name} is what you intended."""
                )
                extra[field_name] = values.pop(field_name)

        invalid_model_kwargs = all_required_field_names.intersection(extra.keys())
        if invalid_model_kwargs:
            raise ValueError(
                f"Parameters {invalid_model_kwargs} should be specified explicitly. "
                f"Instead they were passed in as part of `model_kwargs` parameter."
            )

        values["model_kwargs"] = extra
        return values

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        values["openai_api_key"] = get_from_dict_or_env(
            values, "openai_api_key", "OPENAI_API_KEY"
        )
        values["openai_api_base"] = get_from_dict_or_env(
            values,
            "openai_api_base",
            "OPENAI_API_BASE",
            default="",
        )
        values["openai_api_type"] = get_from_dict_or_env(
            values,
            "openai_api_type",
            "OPENAI_API_TYPE",
            default="",
        )
        values["openai_proxy"] = get_from_dict_or_env(
            values,
            "openai_proxy",
            "OPENAI_PROXY",
            default="",
        )
        if values["openai_api_type"] in ("azure", "azure_ad", "azuread"):
            default_api_version = "2022-12-01"
        else:
            default_api_version = ""
        values["openai_api_version"] = get_from_dict_or_env(
            values,
            "openai_api_version",
            "OPENAI_API_VERSION",
            default=default_api_version,
        )
        values["openai_organization"] = get_from_dict_or_env(
            values,
            "openai_organization",
            "OPENAI_ORGANIZATION",
            default="",
        )
        try:
            import openai

            values["client"] = openai.Embedding
        except ImportError:
            raise ImportError(
                "Could not import openai python package. "
                "Please install it with `pip install openai`."
            )
        return values

    @property
    def _invocation_params(self) -> Dict:
        openai_args = {
            "model": self.model,
            "request_timeout": self.request_timeout,
            "headers": self.headers,
            "api_key": self.openai_api_key,
            "organization": self.openai_organization,
            "api_base": self.openai_api_base,
            "api_type": self.openai_api_type,
            "api_version": self.openai_api_version,
            **self.model_kwargs,
        }
        if self.openai_api_type in ("azure", "azure_ad", "azuread"):
            openai_args["engine"] = self.deployment
        if self.openai_proxy:
            try:
                import openai
            except ImportError:
                raise ImportError(
                    "Could not import openai python package. "
                    "Please install it with `pip install openai`."
                )

            openai.proxy = {
                "http": self.openai_proxy,
                "https": self.openai_proxy,
            }  # type: ignore[assignment]  # noqa: E501
        return openai_args

    def _chunk_tokens(self, texts: Sequence[str]) -> Tuple[List[List], List[int]]:
        """Tokenize and chunk texts to fit in the model's context window."""
        if not self.embedding_ctx_length:
            raise ValueError(
                "embedding_ctx_length must be defined to use _get_len_safe_embeddings."
            )

        try:
            import tiktoken
        except ImportError:
            raise ImportError(
                "Could not import tiktoken python package. "
                "This is needed in order to for OpenAIEmbeddings. "
                "Please install it with `pip install tiktoken`."
            )

        tokens = []
        indices = []
        model_name = self.tiktoken_model_name or self.model
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            logger.warning("Warning: model not found. Using cl100k_base encoding.")
            model = "cl100k_base"
            encoding = tiktoken.get_encoding(model)
        for i, text in enumerate(texts):
            if self.model.endswith("001"):
                # See: https://github.com/openai/openai-python/issues/418#issuecomment-1525939500
                # replace newlines, which can negatively affect performance.
                text = text.replace("\n", " ")
            token = encoding.encode(
                text,
                allowed_special=self.allowed_special,
                disallowed_special=self.disallowed_special,
            )
            for j in range(0, len(token), self.embedding_ctx_length):
                tokens.append(token[j : j + self.embedding_ctx_length])
                indices.append(i)
        return tokens, indices

    def _batch_embed(
        self, inputs: Sequence, *, chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        batched_embeddings: List[List[float]] = []
        _chunk_size = chunk_size or self.chunk_size
        _iter = range(0, len(inputs), _chunk_size)
        if self.show_progress_bar:
            try:
                import tqdm

                _iter = tqdm.tqdm(_iter)
            except ImportError:
                pass

        for i in _iter:
            response = embed_with_retry(
                self,
                input=inputs[i : i + _chunk_size],
                **self._invocation_params,
            )
            batched_embeddings.extend(r["embedding"] for r in response["data"])
        return batched_embeddings

    async def _abatch_embed(
        self, inputs: Sequence, *, chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        batched_embeddings: List[List[float]] = []
        _chunk_size = chunk_size or self.chunk_size
        _iter = range(0, len(inputs), _chunk_size)
        if self.show_progress_bar:
            try:
                import tqdm

                _iter = tqdm.tqdm(_iter)
            except ImportError:
                pass

        for i in _iter:
            response = await async_embed_with_retry(
                self,
                input=inputs[i : i + _chunk_size],
                **self._invocation_params,
            )
            batched_embeddings.extend(r["embedding"] for r in response["data"])
        return batched_embeddings

    # please refer to
    # https://github.com/openai/openai-cookbook/blob/main/examples/Embedding_long_inputs.ipynb
    def _get_len_safe_embeddings(
        self, texts: List[str], *, engine: str, chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        tokens, indices = self._chunk_tokens(texts)
        batched_embeddings = self._batch_embed(tokens, chunk_size=chunk_size)
        results: List[List[List[float]]] = [[] for _ in range(len(texts))]
        num_tokens_in_batch: List[List[int]] = [[] for _ in range(len(texts))]
        for idx, tokens_i, batched_emb in zip(indices, tokens, batched_embeddings):
            results[idx].append(batched_emb)
            num_tokens_in_batch[idx].append(len(tokens_i))

        embeddings = []
        empty_average = embed_with_retry(
            self,
            input="",
            **self._invocation_params,
        )[
            "data"
        ][0]["embedding"]
        for _result, num_tokens in zip(results, num_tokens_in_batch):
            if len(_result) == 0:
                average = empty_average
            else:
                average = np.average(_result, axis=0, weights=num_tokens)
            normalized = (average / np.linalg.norm(average)).tolist()
            embeddings.append(normalized)

        return embeddings

    # please refer to
    # https://github.com/openai/openai-cookbook/blob/main/examples/Embedding_long_inputs.ipynb
    async def _aget_len_safe_embeddings(
        self, texts: List[str], *, engine: str, chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        tokens, indices = self._chunk_tokens(texts)
        batched_embeddings = await self._abatch_embed(tokens, chunk_size=chunk_size)

        results: List[List[List[float]]] = [[] for _ in range(len(texts))]
        num_tokens_in_batch: List[List[int]] = [[] for _ in range(len(texts))]
        for idx, tokens_i, batched_emb in zip(indices, tokens, batched_embeddings):
            results[idx].append(batched_emb)
            num_tokens_in_batch[idx].append(len(tokens_i))

        embeddings = []
        empty_average = (
            await async_embed_with_retry(
                self,
                input="",
                **self._invocation_params,
            )
        )["data"][0]["embedding"]
        for _result, num_tokens in zip(results, num_tokens_in_batch):
            if len(_result) == 0:
                average = empty_average
            else:
                average = np.average(_result, axis=0, weights=num_tokens)
            normalized = (average / np.linalg.norm(average)).tolist()
            embeddings.append(normalized)

        return embeddings

    def embed_documents(
        self, texts: List[str], chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        """Call out to OpenAI's embedding endpoint for embedding search docs.

        Args:
            texts: The list of texts to embed.
            chunk_size: The chunk size of embeddings. If None, will use the chunk size
                specified by the class.

        Returns:
            List of embeddings, one for each text.
        """
        # NOTE: to keep things simple, as long as the embedding_ctx_length is defined,
        # we assume the list may contain texts longer than the maximum context and
        # use length-safe embedding function.
        if self.embedding_ctx_length:
            return self._get_len_safe_embeddings(
                texts, engine=self.deployment, chunk_size=chunk_size
            )

        embeddings = self._batch_embed(texts, chunk_size=chunk_size)
        return [(np.array(e) / np.linalg.norm(e)).tolist() for e in embeddings]

    async def aembed_documents(
        self, texts: List[str], chunk_size: Optional[int] = 0
    ) -> List[List[float]]:
        """Call out to OpenAI's embedding endpoint async for embedding search docs.

        Args:
            texts: The list of texts to embed.
            chunk_size: The chunk size of embeddings. If None, will use the chunk size
                specified by the class.

        Returns:
            List of embeddings, one for each text.
        """
        # NOTE: to keep things simple, as long as the embedding_ctx_length is defined,
        #       we assume the list may contain texts longer than the maximum context and
        #       use length-safe embedding function.
        if self.embedding_ctx_length:
            return await self._aget_len_safe_embeddings(texts, engine=self.deployment)

        embeddings = await self._abatch_embed(texts, chunk_size=chunk_size)
        return [(np.array(e) / np.linalg.norm(e)).tolist() for e in embeddings]

    def embed_query(self, text: str) -> List[float]:
        """Call out to OpenAI's embedding endpoint for embedding query text.

        Args:
            text: The text to embed.

        Returns:
            Embedding for the text.
        """
        return self.embed_documents([text])[0]

    async def aembed_query(self, text: str) -> List[float]:
        """Call out to OpenAI's embedding endpoint async for embedding query text.

        Args:
            text: The text to embed.

        Returns:
            Embedding for the text.
        """
        embeddings = await self.aembed_documents([text])
        return embeddings[0]