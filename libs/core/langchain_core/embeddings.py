import asyncio
import warnings
from abc import ABC, abstractmethod
from inspect import signature
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.callbacks.base import Callbacks
from langchain_core.callbacks.manager import (
    AsyncCallbackManager,
    AsyncCallbackManagerForEmbeddingRun,
    CallbackManager,
    CallbackManagerForEmbeddingRun,
)


class Embeddings(ABC):
    """Interface for embedding models."""

    _new_arg_supported: bool = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__()
        if cls.embed_documents != Embeddings.embed_documents:
            warnings.warn(
                "Embedding models must implement abstract `_embed_documents` method"
                " instead of `embed_documents`",
                DeprecationWarning,
            )
            swap = cls.embed_documents
            cls.embed_documents = Embeddings.embed_documents  # type: ignore[assignment]
            cls._embed_documents = swap  # type: ignore[assignment]
        if (
            hasattr(cls, "aembed_documents")
            and cls.aembed_documents != Embeddings.aembed_documents
        ):
            warnings.warn(
                "Embedding models must implement abstract `_aembed_documents` method"
                " instead of `aembed_documents`",
                DeprecationWarning,
            )
            aswap = cls.aembed_documents
            cls.aembed_documents = (  # type: ignore[assignment]
                Embeddings.aembed_documents
            )
            cls._aembed_documents = aswap  # type: ignore[assignment]
        parameters = signature(cls._embed_documents).parameters
        cls._new_arg_supported = parameters.get("run_managers") is not None

    @abstractmethod
    def _embed_documents(
        self,
        texts: List[str],
        *,
        run_managers: Sequence[CallbackManagerForEmbeddingRun],
    ) -> List[List[float]]:
        """Embed search docs."""

    @abstractmethod
    def _embed_query(
        self,
        text: str,
        *,
        run_manager: CallbackManagerForEmbeddingRun,
    ) -> List[float]:
        """Embed query text."""

    async def _aembed_documents(
        self,
        texts: List[str],
        *,
        run_managers: Sequence[AsyncCallbackManagerForEmbeddingRun],
    ) -> List[List[float]]:
        """Embed search docs."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support async")

    async def _aembed_query(
        self,
        text: str,
        *,
        run_manager: AsyncCallbackManagerForEmbeddingRun,
    ) -> List[float]:
        """Embed query text."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support async")

    def embed_documents(
        self,
        texts: List[str],
        *,
        callbacks: Callbacks = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[List[float]]:
        """Embed search docs."""
        callback_manager = CallbackManager.configure(
            callbacks, None, inheritable_tags=tags, inheritable_metadata=metadata
        )
        run_managers: List[
            CallbackManagerForEmbeddingRun
        ] = callback_manager.on_embedding_start(
            {},  # TODO: make embeddings serializable
            texts,
        )
        try:
            if self._new_arg_supported:
                result = self._embed_documents(
                    texts,
                    run_managers=run_managers,
                )
            else:
                result = self._embed_documents(texts)  # type: ignore[call-arg]
        except Exception as e:
            for run_manager in run_managers:
                run_manager.on_embedding_error(e)
            raise e
        else:
            for single_result, run_manager in zip(result, run_managers):
                run_manager.on_embedding_end(
                    single_result,
                )
            return result

    def embed_query(
        self,
        text: str,
        *,
        callbacks: Callbacks = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[float]:
        """Embed query text."""
        callback_manager = CallbackManager.configure(
            callbacks, None, inheritable_tags=tags, inheritable_metadata=metadata
        )
        run_managers: List[
            CallbackManagerForEmbeddingRun
        ] = callback_manager.on_embedding_start(
            {},  # TODO: make embeddings serializable
            [text],
        )
        try:
            if self._new_arg_supported:
                result = self._embed_query(text, run_manager=run_managers[0])
            else:
                result = self._embed_query(text)  # type: ignore[call-arg]
        except Exception as e:
            run_managers[0].on_embedding_error(e)
            raise e
        else:
            run_managers[0].on_embedding_end(
                result,
            )
            return result

    async def aembed_documents(
        self,
        texts: List[str],
        *,
        callbacks: Callbacks = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[List[float]]:
        """Asynchronously embed search docs."""
        callback_manager = AsyncCallbackManager.configure(
            callbacks, None, inheritable_tags=tags, inheritable_metadata=metadata
        )
        run_managers: List[
            AsyncCallbackManagerForEmbeddingRun
        ] = await callback_manager.on_embedding_start(
            {},  # TODO: make embeddings serializable
            texts,
        )
        try:
            if self._new_arg_supported:
                result = await self._aembed_documents(
                    texts,
                    run_managers=run_managers,
                )
            else:
                result = await self._aembed_documents(texts)  # type: ignore[call-arg]
        except Exception as e:
            tasks = [run_manager.on_embedding_error(e) for run_manager in run_managers]
            await asyncio.gather(*tasks)
            raise e
        else:
            tasks = [
                run_manager.on_embedding_end(
                    single_result,
                )
                for run_manager, single_result in zip(run_managers, result)
            ]
            await asyncio.gather(*tasks)
            return result

    async def aembed_query(
        self,
        text: str,
        *,
        callbacks: Callbacks = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[float]:
        """Asynchronously embed query text."""
        callback_manager = AsyncCallbackManager.configure(
            callbacks, None, inheritable_tags=tags, inheritable_metadata=metadata
        )
        run_managers: List[
            AsyncCallbackManagerForEmbeddingRun
        ] = await callback_manager.on_embedding_start(
            {},  # TODO: make embeddings serializable
            [text],
        )
        try:
            if self._new_arg_supported:
                result = await self._aembed_query(
                    text,
                    run_manager=run_managers[0],
                )
            else:
                result = await self._aembed_query(text)  # type: ignore[call-arg]
        except Exception as e:
            await run_managers[0].on_embedding_error(e)
            raise e
        else:
            await run_managers[0].on_embedding_end(
                result,
            )
            return result
