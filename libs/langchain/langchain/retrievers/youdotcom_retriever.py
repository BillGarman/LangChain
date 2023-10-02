import os

from typing import List, Any, Dict, Optional
from pydantic.class_validators import root_validator

from langchain.callbacks.manager import CallbackManagerForRetrieverRun
from langchain.schema import BaseRetriever, Document


class YouRetriever(BaseRetriever):
    """`You` retriever that uses You.com's search API.

    To connect to the You.com api requires an API key which you can get by emailing BLAHBLAHBLAH@you.com.
    You can check out our Swagger docs at https://api.ydc-index.io/docs/docs/index.html.

    You need to set the environment variable `YDC_API_KEY` for retriever to operate.
    """
    ydc_api_key: Optional[str] = None


    @root_validator(pre=True)
    def validate_client(
        cls,
        values: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not os.getenv("YDC_API_KEY"):
            raise RuntimeError("YDC_API_KEY environment variable not found")
        else:
            values["ydc_api_key"] = os.get("YDC_API_KEY")
        return values

    def add_documents(self, docs: List[Document], **kwargs: Any) -> List[str]:
        raise NotImplementedError("The You.com API does not support adding documents to the index")

    def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        import requests

        headers = {"X-API-Key": self.ydc_api_key}
        results = requests.get(
            f"https://api.ydc-index.io/search?query={query}",
            headers=headers,
        ).json()


        docs = []
        for hit in results["hits"]:
            for snippet in hit["snippets"]:
                docs.append(Document(page_content=snippet))
        return docs
