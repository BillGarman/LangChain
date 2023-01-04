"""Functionality for splitting text."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, List, Optional

from langchain.docstore.document import Document

logger = logging.getLogger()


class TextSplitter(ABC):
    """Interface for splitting text into chunks."""

    def __init__(
        self,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
    ):
        """Create a new TextSplitter."""
        if chunk_overlap > chunk_size:
            raise ValueError(
                f"Got a larger chunk overlap ({chunk_overlap}) than chunk size "
                f"({chunk_size}), should be smaller."
            )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._length_function = length_function

    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        """Split text into multiple components."""

    def create_documents(
        self, texts: List[str], metadatas: Optional[List[dict]] = None
    ) -> List[Document]:
        """Create documents from a list of texts."""
        _metadatas = metadatas or [{}] * len(texts)
        documents = []
        for i, text in enumerate(texts):
            for chunk in self.split_text(text):
                documents.append(Document(page_content=chunk, metadata=_metadatas[i]))
        return documents

    def _merge_splits(self, splits: Iterable[str], separator: str) -> List[str]:
        # We now want to combine these smaller pieces into medium size
        # chunks to send to the LLM.
        docs = []
        current_doc: List[str] = []
        total = 0
        for d in splits:
            _len = self._length_function(d)
            if total + _len >= self._chunk_size:
                if total > self._chunk_size:
                    logger.warning(
                        f"Created a chunk of size {total}, "
                        f"which is longer than the specified {self._chunk_size}"
                    )
                if len(current_doc) > 0:
                    docs.append(separator.join(current_doc))
                    while total > self._chunk_overlap:
                        total -= self._length_function(current_doc[0])
                        current_doc = current_doc[1:]
            current_doc.append(d)
            total += _len
        docs.append(separator.join(current_doc))
        return docs

    @classmethod
    def from_huggingface_tokenizer(cls, tokenizer: Any, **kwargs: Any) -> TextSplitter:
        """Text splitter that uses HuggingFace tokenizer to count length."""
        try:
            from transformers import PreTrainedTokenizerBase

            if not isinstance(tokenizer, PreTrainedTokenizerBase):
                raise ValueError(
                    "Tokenizer received was not an instance of PreTrainedTokenizerBase"
                )

            def _huggingface_tokenizer_length(text: str) -> int:
                return len(tokenizer.encode(text))

        except ImportError:
            raise ValueError(
                "Could not import transformers python package. "
                "Please it install it with `pip install transformers`."
            )
        return cls(length_function=_huggingface_tokenizer_length, **kwargs)

    @classmethod
    def from_tiktoken_encoder(
        cls, encoding_name: str = "gpt2", **kwargs: Any
    ) -> TextSplitter:
        """Text splitter that uses tiktoken encoder to count length."""
        try:
            import tiktoken
        except ImportError:
            raise ValueError(
                "Could not import tiktoken python package. "
                "This is needed in order to calculate max_tokens_for_prompt. "
                "Please it install it with `pip install tiktoken`."
            )
        # create a GPT-3 encoder instance
        enc = tiktoken.get_encoding(encoding_name)

        def _tiktoken_encoder(text: str) -> int:
            return len(enc.encode(text))

        return cls(length_function=_tiktoken_encoder, **kwargs)


class CharacterTextSplitter(TextSplitter):
    """Implementation of splitting text that looks at characters."""

    def __init__(self, separator: str = "\n\n", **kwargs: Any):
        """Create a new TextSplitter."""
        super().__init__(**kwargs)
        self._separator = separator

    def split_text(self, text: str) -> List[str]:
        """Split incoming text and return chunks."""
        # First we naively split the large input into a bunch of smaller ones.
        splits = text.split(self._separator)
        return self._merge_splits(splits, self._separator)


class IterativeCharacterTextSplitter(TextSplitter):
    """Implementation of splitting text that looks at characters.

    Iteratively tries to split by different characters to find one
    that works.
    """

    def __init__(self, separators: Optional[List[str]] = None, **kwargs: Any):
        """Create a new TextSplitter."""
        super().__init__(**kwargs)
        self._separators = separators or ["\n\n", "\n", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """Split incoming text and return chunks."""
        for _separator in self._separators:
            # Try to split the text by the chosen separator
            splits = text.split(_separator)
            # Check to see if the largest chunk is under the limit
            if max([len(s) for s in splits]) < self._chunk_size:
                # If it is, use it!
                return self._merge_splits(splits, _separator)
        # If nothing worked, use the last separator
        _separator = self._separators[-1]
        splits = text.split(_separator)
        return self._merge_splits(splits, _separator)


class NLTKTextSplitter(TextSplitter):
    """Implementation of splitting text that looks at sentences using NLTK."""

    def __init__(self, separator: str = "\n\n", **kwargs: Any):
        """Initialize the NLTK splitter."""
        super().__init__(**kwargs)
        try:
            from nltk.tokenize import sent_tokenize

            self._tokenizer = sent_tokenize
        except ImportError:
            raise ImportError(
                "NLTK is not installed, please install it with `pip install nltk`."
            )
        self._separator = separator

    def split_text(self, text: str) -> List[str]:
        """Split incoming text and return chunks."""
        # First we naively split the large input into a bunch of smaller ones.
        splits = self._tokenizer(text)
        return self._merge_splits(splits, self._separator)


class SpacyTextSplitter(TextSplitter):
    """Implementation of splitting text that looks at sentences using Spacy."""

    def __init__(
        self, separator: str = "\n\n", pipeline: str = "en_core_web_sm", **kwargs: Any
    ):
        """Initialize the spacy text splitter."""
        super.__init__(**kwargs)
        try:
            import spacy
        except ImportError:
            raise ImportError(
                "Spacy is not installed, please install it with `pip install spacy`."
            )
        self._tokenizer = spacy.load(pipeline)
        self._separator = separator

    def split_text(self, text: str) -> List[str]:
        """Split incoming text and return chunks."""
        splits = (str(s) for s in self._tokenizer(text).sents)
        return self._merge_splits(splits, self._separator)
