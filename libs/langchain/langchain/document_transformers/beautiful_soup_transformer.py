from typing import Any, List, Sequence

from bs4 import BeautifulSoup

from langchain.schema import BaseDocumentTransformer, Document


class BeautifulSoupTransformer(BaseDocumentTransformer):
    """Transform HTML content by extracting specific tags and removing unwanted ones.

    Example:
        .. code-block:: python
            from langchain.document_transformers import BeautifulSoupTransformer
            bs4_transformer = BeautifulSoupTransformer()
            docs_transformed = bs4_transformer.transform_documents(docs)
    """

    def transform_documents(
        self,
        documents: Sequence[Document],
        unwanted_tags: List[str] = ["script", "style"],
        tags_to_extract: List[str] = ["p", "li", "div", "a"],
        remove_lines: bool = True,
        **kwargs: Any,
    ) -> Sequence[Document]:

        try:
            import bs4
        except ImportError:
            raise ImportError(
                """bs4 package not found, please 
                install it with `pip install -q beautifulsoup4`"""
            )

        for doc in documents:
            cleaned_content = doc.page_content

            cleaned_content = self.remove_unwanted_tags(
                cleaned_content, unwanted_tags)

            cleaned_content = self.extract_tags(
                cleaned_content, tags_to_extract)

            if remove_lines:
                cleaned_content = self.remove_unnecessary_lines(
                    cleaned_content)

            doc.page_content = cleaned_content

        return documents

    @staticmethod
    def remove_unwanted_tags(html_content, unwanted_tags) -> str:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()
        return str(soup)

    @staticmethod
    def extract_tags(html_content, tags) -> str:
        soup = BeautifulSoup(html_content, "html.parser")
        text_parts = []
        for tag in tags:
            elements = soup.find_all(tag)
            for element in elements:
                if tag == "a":
                    href = element.get("href")
                    if href:
                        text_parts.append(f"{element.get_text()} ({href})")
                    else:
                        text_parts.append(element.get_text())
                else:
                    text_parts.append(element.get_text())
        return " ".join(text_parts)

    @staticmethod
    def remove_unnecessary_lines(content) -> str:
        lines = content.split("\n")
        stripped_lines = [line.strip() for line in lines]
        non_empty_lines = [line for line in stripped_lines if line]
        seen = set()
        deduped_lines = [
            line for line in non_empty_lines if not (line in seen or seen.add(line))
        ]
        cleaned_content = "".join(deduped_lines)
        return cleaned_content
