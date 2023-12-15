import json
import logging
import threading
from queue import Queue
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.documents import Document

from langchain_community.document_loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class AstraDBLoader(BaseLoader):
    """Load DataStax Astra DB documents."""

    def __init__(
        self,
        collection_name: str,
        token: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        astra_db_client: Optional[Any] = None,  # 'astrapy.db.AstraDB' if passed
        namespace: Optional[str] = None,
        filter_criteria: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
        find_options: Optional[Dict[str, Any]] = None,
        sort: Optional[Dict[str, Any]] = None,
        nb_prefetched: int = 1000,
    ) -> None:
        try:
            from astrapy.db import AstraDB
        except (ImportError, ModuleNotFoundError):
            raise ImportError(
                "Could not import a recent astrapy python package. "
                "Please install it with `pip install --upgrade astrapy`."
            )

        # Conflicting-arg checks:
        if astra_db_client is not None:
            if token is not None or api_endpoint is not None:
                raise ValueError(
                    "You cannot pass 'astra_db_client' to AstraDB if passing "
                    "'token' and 'api_endpoint'."
                )

        self.filter = filter_criteria
        self.projection = projection
        self.find_options = find_options or {}
        self.sort = sort
        self.nb_prefetched = nb_prefetched

        if astra_db_client is not None:
            astra_db = astra_db_client
        else:
            astra_db = AstraDB(
                token=token,
                api_endpoint=api_endpoint,
                namespace=namespace,
            )
        self.collection = astra_db.collection(collection_name)

    def load(self) -> List[Document]:
        """Eagerly load the content."""
        return list(self.lazy_load())

    def lazy_load(self) -> Iterator[Document]:
        queue = Queue(self.nb_prefetched)
        t = threading.Thread(target=self.fetch_results, args=(queue,))
        t.start()
        while True:
            doc = queue.get()
            if doc is None:
                break
            yield doc
        t.join()

    def fetch_results(self, queue: Queue) -> None:
        has_more = self.fetch_page_result(queue)
        while has_more:
            has_more = self.fetch_page_result(queue)
        queue.put(None)

    def fetch_page_result(self, queue: Queue) -> bool:
        res = self.collection.find(
            filter=self.filter,
            options=self.find_options,
            projection=self.projection,
            sort=self.sort,
        )
        self.find_options["pageState"] = res["data"].get("nextPageState")
        docs = res["data"]["documents"]
        for doc in docs:
            queue.put(
                Document(
                    page_content=json.dumps(doc),
                    metadata={
                        "namespace": self.collection.astra_db.namespace,
                        "api_endpoint": self.collection.astra_db.base_url,
                        "collection": self.collection.collection_name,
                    },
                )
            )
        if len(docs) == 20 and self.sort:
            self.find_options["skip"] = self.find_options.get("skip", 0) + 20
            if "limit" not in self.find_options:
                return True
            limit = self.find_options["limit"]
            if limit == 20:
                return False
            self.find_options["limit"] = limit - 20
            return True
        return self.find_options["pageState"] is not None
