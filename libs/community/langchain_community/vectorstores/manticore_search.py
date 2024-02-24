from __future__ import annotations

import uuid
import json
import logging
from hashlib import sha1
from threading import Thread
from typing import Any, Dict, Iterable, List, Optional, Type

from manticoresearch.api import search_api

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseSettings
from langchain_core.vectorstores import VectorStore

logger = logging.getLogger()
DEFAULT_K = 4  # Number of Documents to return.


class ManticoreSearchSettings(BaseSettings):
    host: str = "localhost"
    port: int = 9308

    username: Optional[str] = None
    password: Optional[str] = None

    # database: str = "Manticore"
    table: str = "langchain"

    column_map: Dict[str, str] = {
        "id": "id",
        "uuid": "uuid",
        "document": "document",
        "embedding": "embedding",
        "metadata": "metadata",
    }

    # A mandatory setting; currently, only hnsw is supported.
    knn_type: str = "hnsw"

    # A mandatory setting that specifies the dimensions of the vectors being indexed.
    knn_dims: int = None  # Defaults autodetect

    # A mandatory setting that specifies the distance function used by the HNSW index.
    hnsw_similarity: str = 'L2'  # Acceptable values are: L2 (Squared L2), IP (Inner product), COSINE (Cosine similarity)

    # An optional setting that defines the maximum amount of outgoing connections in the graph.
    hnsw_m: int = 16  # The default is 16.

    # An optional setting that defines a construction time/accuracy trade-off.
    hnsw_ef_construction = 0

    def get_connection_string(self) -> str:
        return 'http://' + self.host + ':' + str(self.port)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    class Config:
        env_file = ".env"
        env_prefix = "manticore_"
        env_file_encoding = "utf-8"


class ManticoreSearch(VectorStore):
    """
    `ManticoreSearch Engine` vector store.

    To use, you should have the ``manticoresearch`` python package installed.

    Example:
        .. code-block:: python

                from langchain_community.vectorstores import Manticore
                from langchain_community.embeddings.openai import OpenAIEmbeddings

                embeddings = OpenAIEmbeddings()
                vectorstore = ManticoreSearch(embeddings)
    """

    def __init__(
            self,
            embedding_function: Optional[Embeddings] = None,
            config: Optional[ManticoreSearchSettings] = None,
            **kwargs: Any,
    ) -> None:
        """
        ManticoreSearch Wrapper to LangChain

        embedding_function (Embeddings):
        config (ManticoreSearchSettings): Configuration of ManticoreSearch Client
        Other keyword arguments will pass into Configuration of API client
            [manticoresearch-python](https://github.com/manticoresoftware/manticoresearch-python)
        """
        try:
            import manticoresearch.api_client as API
            import manticoresearch.api as ENDPOINTS
        except ImportError:
            raise ImportError(
                "Could not import manticoresearch python package. "
                "Please install it with `pip install manticoresearch`."
            )

        try:
            from tqdm import tqdm
            self.pgbar = tqdm
        except ImportError:
            # Just in case if tqdm is not installed
            self.pgbar = lambda x, **kwargs: x

        super().__init__()

        self.embedding_function = embedding_function
        if config is not None:
            self.config = config
        else:
            self.config = ManticoreSearchSettings()

        assert self.config
        assert self.config.host and self.config.port
        assert (
                self.config.column_map
                # and self.config.database
                and self.config.table
        )

        assert (
                self.config.knn_type
                # and self.config.knn_dims
                # and self.config.hnsw_m
                # and self.config.hnsw_ef_construction
                and self.config.hnsw_similarity
        )

        for k in ["id", "embedding", "document", "metadata", "uuid"]:
            assert k in self.config.column_map

        # Detect embeddings dimension
        if self.config.knn_dims is None:
            self.dim = len(self.embedding_function.embed_query("test"))
        else:
            self.dim = self.config.knn_dims

        # Initialize the schema
        self.schema = f"""\
CREATE TABLE IF NOT EXISTS {self.config.table}(
    {self.config.column_map['id']} bigint,
    {self.config.column_map['document']} text indexed stored,
    {self.config.column_map['embedding']} float_vector knn_type='{self.config.knn_type}' knn_dims='{self.dim}' hnsw_similarity='{self.config.hnsw_similarity}',
    {self.config.column_map['metadata']} json,
    {self.config.column_map['uuid']} text indexed stored
)\
"""

        # Create a connection to ManticoreSearch
        self.configuration = API.Configuration(
            host=self.config.get_connection_string(),
            username=self.config.username,
            password=self.config.password,
            # disabled_client_side_validations=",",
            **kwargs,
        )
        self.connection = API.ApiClient(self.configuration)
        self.client = {
            "index": ENDPOINTS.IndexApi(self.connection),
            "utils": ENDPOINTS.UtilsApi(self.connection),
            "search": ENDPOINTS.SearchApi(self.connection),
        }

        # Create default schema if not exists
        self.client['utils'].sql(self.schema)

    @property
    def embeddings(self) -> Embeddings:
        return self.embedding_function

    def add_texts(
            self,
            texts: Iterable[str],
            metadatas: Optional[List[dict]] = None,
            batch_size: int = 100,
            ids: Optional[Iterable[str]] = None,
            **kwargs: Any,
    ) -> List[str]:
        """
        Insert more texts through the embeddings and add to the VectorStore.

        Args:
            texts: Iterable of strings to add to the VectorStore
            metadata: Optional column data to be inserted
            batch_size: Batch size of insertion
            ids: Optional list of ids to associate with the texts

        Returns:
            List of ids from adding the texts into the VectorStore.
        """
        # Embed and create the documents
        ids = ids or [
            # See https://stackoverflow.com/questions/67219691/python-hash-function-that-returns-32-or-64-bits
            int(sha1(t.encode('utf-8')).hexdigest()[:15], 16)
            for t in texts
        ]
        transac = []
        for i, (text, meta) in enumerate(zip(texts, metadatas)):
            embed = self.embeddings.embed_query(text)
            doc_uuid = str(uuid.uuid1())
            doc = {
                self.config.column_map['document']: text,
                self.config.column_map['embedding']: embed,
                self.config.column_map['metadata']: meta,
                self.config.column_map['uuid']: doc_uuid
            }
            transac.append({"replace": {"index": self.config.table, "id": ids[i], "doc": doc}})

            if len(transac) == batch_size:
                body = '\n'.join(map(json.dumps, transac))
                try:
                    response = self.client['index'].bulk(body)
                    transac = []
                except Exception as e:
                    print(f"Error indexing documents: {e}")

        if len(transac) > 0:
            body = '\n'.join(map(json.dumps, transac))
            try:
                response = self.client['index'].bulk(body)
            except Exception as e:
                print(f"Error indexing documents: {e}")

        return ids

    @classmethod
    def from_texts(
            cls: Type[ManticoreSearch],
            texts: List[str],
            embedding: Embeddings,
            metadatas: Optional[List[Dict[Any, Any]]] = None,
            config: Optional[ManticoreSearchSettings] = None,
            text_ids: Optional[Iterable[str]] = None,
            batch_size: int = 32,
            **kwargs: Any,
    ) -> ManticoreSearch:
        ctx = cls(embedding, config, **kwargs)
        ctx.add_texts(
            texts=texts,
            embedding=embedding,
            ids=text_ids,
            batch_size=batch_size,
            metadatas=metadatas,
            **kwargs,
        )
        return ctx

    @classmethod
    def from_documents(
            cls: Type[ManticoreSearch],
            documents: List[Document],
            embedding: Embeddings,
            config: Optional[ManticoreSearchSettings] = None,
            text_ids: Optional[Iterable[str]] = None,
            batch_size: int = 32,
            **kwargs: Any,
    ) -> ManticoreSearch:
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        return cls.from_texts(
            texts=texts,
            embedding=embedding,
            text_ids=text_ids,
            batch_size=batch_size,
            metadatas=metadatas,
            **kwargs,
        )

    def __repr__(self) -> str:
        """
        Text representation for ManticoreSearch Vector Store, prints backends, username
        and schemas. Easy to use with `str(ManticoreSearch())`

        Returns:
            repr: string to show connection info and data schema
        """
        _repr = f"\033[92m\033[1m{self.config.table} @ "
        _repr += f"http://{self.config.host}:{self.config.port}\033[0m\n\n"
        _repr += f"\033[1musername: {self.config.username}\033[0m\n\nTable Schema:\n"
        _repr += "-" * 51 + "\n"
        for r in self.client['utils'].sql(f"DESCRIBE {self.config.table}")[0]['data']:
            _repr += (
                f"|\033[94m{r['Field']:24s}\033[0m|\033[96m{r['Type'] + ' ' + r['Properties']:24s}\033[0m|\n"
            )
        _repr += "-" * 51 + "\n"
        return _repr

    def similarity_search(
            self, query: str,
            k: int = DEFAULT_K,
            **kwargs: Any
    ) -> List[Document]:
        """Perform a similarity search with ManticoreSearch

        Args:
            query (str): query string
            k (int, optional): Top K neighbors to retrieve. Defaults to 4.

        Returns:
            List[Document]: List of Documents
        """
        return self.similarity_search_by_vector(self.embedding_function.embed_query(query), k, **kwargs)

    def similarity_search_by_vector(
            self,
            embedding: List[float],
            k: int = DEFAULT_K,
            **kwargs: Any,
    ) -> List[Document]:
        """Perform a similarity search with ManticoreSearch by vectors

        Args:
            embedding (List[float]): Embedding vector
            k (int, optional): Top K neighbors to retrieve. Defaults to 4.

        Returns:
            List[Document]: List of documents
        """

        # Build kNN-request
        request_knn = dict(
            field=self.config.column_map['embedding'],
            k=k,
            query_vector=embedding
        )

        # Build search request
        request = dict(
            index=self.config.table,
            knn=request_knn
        )

        # Execute request and convert response to langchain.Document format
        try:
            return [
                Document(
                    page_content=r[self.config.column_map["document"]],
                    metadata=r[self.config.column_map["metadata"]],
                )
                for r in self.client["search"].search(request, **kwargs).hits.hits
            ]
        except Exception as e:
            logger.error(f"\033[91m\033[1m{type(e)}\033[0m \033[95m{str(e)}\033[0m")
            return []

    def drop(self) -> None:
        """
        Helper function: Drop data
        """
        self.client['utils'].sql(
            f"DROP TABLE IF EXISTS {self.config.table}"
        )

    @property
    def metadata_column(self) -> str:
        return self.config.column_map["metadata"]


if __name__ == "__main__":
    from langchain_community.embeddings import OllamaEmbeddings

    config = ManticoreSearchSettings()
    embedding = OllamaEmbeddings(model='llama2')
    store = ManticoreSearch(embedding_function=embedding, config=config)
    print(store)

    test = store.similarity_search('test')
    print(test)
