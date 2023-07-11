"""Module contains common parsers for PDFs."""
import json
from typing import Any, Iterator, Mapping, Optional, Union

from langchain.document_loaders.base import BaseBlobParser
from langchain.utils import get_from_env
from langchain.document_loaders.blob_loaders import Blob
from langchain.schema import Document


class DoctranQAParser(BaseBlobParser):
    """Extracts metadata from text documents using doctran."""

    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key
        try:
            from doctran import Doctran, ExtractProperty
            self.doctran = Doctran(openai_api_key=openai_api_key)
        except ImportError:
            raise ImportError("Install doctran to use this parser. (pip install doctran)")

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """Lazily parse the blob."""
        if self.openai_api_key:
            openai_api_key = self.openai_api_key
        else:
            openai_api_key = get_from_env("openai_api_key", "OPENAI_API_KEY")
        doctran_doc = self.doctran.parse(content=blob.as_string()).interrogate().execute()
        questions_and_answers = doctran_doc.extracted_properties.get("questions_and_answers")
        yield Document(page_content=blob.as_string(), metadata={"questions_and_answers": questions_and_answers, "source": blob.source})
