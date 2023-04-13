"""Implementations of generic use parsers."""
import magic
from typing import Mapping, Callable, Generator

from langchain.document_loaders.base import Blob
from langchain.schema import Document, BaseBlobParser


class MimeTypeBasedParser(BaseBlobParser):
    """A parser that uses mime-types to determine strategy to use to parse a blob.

    This parser is useful for simple pipelines where the mime-type is sufficient to determine
    how to parse a blob.

    To use, configure handlers based on mime-types and pass them to the initializer.

    Example:

        >>> from langchain.document_loaders.parsers.generic import MimeTypeBasedParser
        >>> from langchain.document_loaders.parsers.unstructured import UnstructuredParser
        >>> from langchain.document_loaders.parsers.image import ImageParser
        >>> from langchain.document_loaders.parsers.pdf import PDFParser
        >>> from langchain.document_loaders.parsers.office import OfficeParser

        >>> parser = MimeTypeBasedParser({
        ...     "text/plain": UnstructuredParser(),
        ...     "image/png": ImageParser(),
        ...     "application/pdf": PDFParser(),
        ...     "application/vnd.openxmlformats-officedocument.wordprocessingml.document": OfficeParser(),
        ... })
        >>> parser.parse(Blob(data=b"Hello world", mimetype="text/plain"))
        [Document(page_content='Hello world', metadata={})]
    """

    def __init__(self, handlers: Mapping[str, Callable[[Blob], Document]]) -> None:
        """A parser based on mime-types.

        Args:
            handlers: A mapping from mime-types to functions that take a blob, parse it and
                      return a document.
        """
        self.handlers = handlers

    def parse(self, blob: Blob) -> Generator[Document, None, None]:
        """Load documents from a file."""
        # TODO(Eugene): Restrict to first 2048 bytes
        mime_type = magic.from_buffer(blob.data, mime=True) if blob.mimetype else blob

        if mime_type in self.handlers:
            handler = self.handlers[mime_type]
            document = handler(blob)
            yield document
        else:
            raise ValueError(f"Unsupported mime type: {mime_type}")
