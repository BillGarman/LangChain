from __future__ import annotations
import asyncio
from functools import partial

import struct
from collections import OrderedDict

import enum
import json
import logging
import uuid
import gpudb

from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
)
from enum import Enum

from langchain.schema.document import Document

from langchain.vectorstores.base import VectorStore
from langchain.embeddings.base import Embeddings

from gpudb import GPUdb
from langchain.vectorstores.utils import maximal_marginal_relevance
import numpy as np

class DistanceStrategy(str, enum.Enum):
    """Enumerator of the Distance strategies."""

    EUCLIDEAN = "l2"
    COSINE = "cosine"
    MAX_INNER_PRODUCT = "inner"


def _results_to_docs(docs_and_scores: Any) -> List[Document]:
    """Return docs from docs and scores."""
    return [doc for doc, _ in docs_and_scores]


class Dimension(int, Enum):
    """Some default dimensions for known embeddings."""
    OPENAI = 1536

    
DEFAULT_DISTANCE_STRATEGY = DistanceStrategy.EUCLIDEAN

_LANGCHAIN_DEFAULT_SCHEMA_NAME = "langchain"  ## Default Kinetica schema name
_LANGCHAIN_DEFAULT_COLLECTION_NAME = "langchain_kinetica_embeddings"  ## Default Kinetica table name


class Kinetica(VectorStore):
    """Kinetica vector store class which extends the `VectorStore` class

    """

    def __init__(
        self,
        db: GPUdb,
        embedding_function: Embeddings,
        dimensions: int,
        collection_name: str = _LANGCHAIN_DEFAULT_COLLECTION_NAME,
        schema_name: str = _LANGCHAIN_DEFAULT_SCHEMA_NAME,
        distance_strategy: DistanceStrategy = DEFAULT_DISTANCE_STRATEGY,
        pre_delete_collection: bool = False,
        logger: Optional[logging.Logger] = None,
        relevance_score_fn: Optional[Callable[[float], float]] = None,
    ) -> None:
        """Constructor for the Kinetica class

        Args:
            db (GPUdb): a `GPUdb` instance
            embedding_function (Embeddings): embedding function to use
            dimensions (int): number of dimensions in the vector
            collection_name (str, optional): the Kinetica table name. Defaults to _LANGCHAIN_DEFAULT_COLLECTION_NAME.
            schema_name (str, optional): the Kinetica table name. Defaults to _LANGCHAIN_DEFAULT_SCHEMA_NAME.
            distance_strategy (DistanceStrategy, optional): _description_. Defaults to DEFAULT_DISTANCE_STRATEGY.
            pre_delete_collection (bool, optional): _description_. Defaults to False.
            logger (Optional[logging.Logger], optional): _description_. Defaults to None.
        """
        self.dimensions = int(Dimension.OPENAI) if dimensions is None or type(dimensions) != int or dimensions <= 0 else dimensions

        self._db = db
        self.embedding_function = embedding_function
        self.dimensions = dimensions
        self.collection_name = collection_name
        self.schema_name = schema_name
        self._distance_strategy = distance_strategy
        self.pre_delete_collection = pre_delete_collection
        self.logger = logger or logging.getLogger(__name__)
        self.override_relevance_score_fn = relevance_score_fn
        self.__post_init__(db, dimensions)

    def __post_init__(
        self, db, dimensions
    ) -> None:
        """
        Initialize the store.
        """
        dimension_field = f'vector({dimensions})'

        if self.pre_delete_collection:
            self.delete_schema()

        self.table_name = self.collection_name
        if self.schema_name is not None and len(self.schema_name) > 0:
            self.table_name = f"{self.schema_name}.{self.collection_name}"

        self.table_schema = [
            ['text', 'string'],
            ['embedding', 'bytes', dimension_field],
            ['metadata', 'string', 'json'],
            ['id', 'string', 'uuid']
            ]

        self.create_schema()
        self.EmbeddingStore: gpudb.GPUdbTable = self.create_tables_if_not_exists()

    @property
    def embeddings(self) -> Embeddings:
        return self.embedding_function

    @classmethod
    def __from(
        cls,
        db: GPUdb,
        texts: List[str],
        embeddings: List[List[float]],
        embedding: Embeddings,
        dimensions: int,
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        collection_name: str = _LANGCHAIN_DEFAULT_COLLECTION_NAME,
        distance_strategy: DistanceStrategy = DEFAULT_DISTANCE_STRATEGY,
        pre_delete_collection: bool = False,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any,
    ) -> Kinetica:
        """ Class method to assist in constructing the `Kinetica` store instance
            using different combinations of parameters

        Args:
            db (GPUdb): a GPUdb instance
            texts (List[str]): The list of texts to generate embeddings for and store
            embeddings (List[List[float]]): _description_
            embedding (Embeddings): the Embedding function
            dimensions (int): The number of dimensions the embeddings have
            metadatas (Optional[List[dict]], optional): List of JSON data associated with each text. Defaults to None.
            ids (Optional[List[str]], optional): List of unique IDs (UUID by default) associated with each text. Defaults to None.
            collection_name (str, optional): Kinetica schema name. Defaults to _LANGCHAIN_DEFAULT_COLLECTION_NAME.
            distance_strategy (DistanceStrategy, optional): Not used for now. Defaults to DEFAULT_DISTANCE_STRATEGY.
            pre_delete_collection (bool, optional): Whether to delete the Kinetica schema or not. Defaults to False.
            logger (Optional[logging.Logger], optional): Logger to use for logging at different levels. Defaults to None.

        Returns:
            Kinetica: An instance of Kinetica class
        """
        dimensions = int(Dimension.OPENAI) if dimensions is None or type(dimensions) != int or dimensions <= 0 else dimensions

        if ids is None:
            ids = [str(uuid.uuid1()) for _ in texts]

        if not metadatas:
            metadatas = [{} for _ in texts]

        store = cls(
            db=db,
            collection_name=collection_name,
            embedding_function=embedding,
            dimensions=dimensions,
            distance_strategy=distance_strategy,
            pre_delete_collection=pre_delete_collection,
            logger=logger,
            **kwargs,
        )

        store.add_embeddings(
            texts=texts, embeddings=embeddings, metadatas=metadatas, ids=ids, **kwargs
        )

        return store

    def create_tables_if_not_exists(self) -> gpudb.GPUdbTable:
        """ Create the table to store the texts and embeddings
        """

        return gpudb.GPUdbTable(_type = self.table_schema, name = self.table_name, db = self._db, options = {"is_replicated": "true"})

    def drop_tables(self) -> None:
        """ Delete the table
        """
        self._db.clear_table(f"{self.table_name}", options={"no_error_if_not_exists": "true"})


    def create_schema(self) -> None:
        """ Create a new Kinetica schema
        """
        self._db.create_schema(self.schema_name)

    def delete_schema(self) -> None:
        """ Delete a Kinetica schema with cascade set to `true`
            This method will delete a schema with all tables in it.
        """
        self.logger.debug("Trying to delete collection")
        self._db.drop_schema(self.schema_name, {"no_error_if_not_exists": "true", "cascade": "true"})

    def add_embeddings(
        self,
        texts: Iterable[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Add embeddings to the vectorstore.

        Args:
            texts: Iterable of strings to add to the vectorstore.
            embeddings: List of list of embedding vectors.
            metadatas: List of metadatas associated with the texts.
            ids: List of ids for the text embedding pairs
            kwargs: vectorstore specific parameters
        """
        if ids is None:
            ids = [str(uuid.uuid1()) for _ in texts]

        records = []
        for text, embedding, metadata, id in zip(texts, embeddings, metadatas, ids):
            buf = struct.pack('%sf' % self.dimensions, *embedding)
            records.append([text, buf, json.dumps(metadata), id])

        self.EmbeddingStore.insert_records(records)

        return ids

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Run more texts through the embeddings and add to the vectorstore.

        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas (JSON data) associated with the texts.
            ids: List of IDs (UUID) for the texts supplied; will be generated if None
            kwargs: vectorstore specific parameters

        Returns:
            List of ids from adding the texts into the vectorstore.
        """
        embeddings = self.embedding_function.embed_documents(list(texts))
        return self.add_embeddings(
            texts=texts, embeddings=embeddings, metadatas=metadatas, ids=ids, **kwargs
        )


    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Run similarity search with Kinetica with distance.

        Args:
            query (str): Query text to search for.
            k (int): Number of results to return. Defaults to 4.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List of Documents most similar to the query.
        """
        embedding = self.embedding_function.embed_query(text=query)
        return self.similarity_search_by_vector(
            embedding=embedding,
            k=k,
            filter=filter,
        )


    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[Tuple[Document, float]]:
        """Return docs most similar to query.

        Args:
            query: Text to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List of Documents most similar to the query and score for each
        """
        embedding = self.embedding_function.embed_query(query)
        docs = self.similarity_search_with_score_by_vector(
            embedding=embedding, k=k, filter=filter
        )
        return docs


    def similarity_search_with_score_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> List[Tuple[Document, float]]:

        resp = self.__query_collection(embedding, k, filter)

        records: OrderedDict = resp["records"]
        results = list(zip(*list(records.values())))

        return self._results_to_docs_and_scores(results)


    def similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[dict] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs most similar to embedding vector.

        Args:
            embedding: Embedding to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List of Documents most similar to the query vector.
        """
        docs_and_scores = self.similarity_search_with_score_by_vector(
            embedding=embedding, k=k, filter=filter
        )
        return [doc for doc, _ in docs_and_scores]


    def _results_to_docs_and_scores(self, results: Any) -> List[Tuple[Document, float]]:
        """Return docs and scores from results."""
        docs = [
            (
                Document(
                    page_content=result[0],
                    metadata=json.loads(result[1]),
                ),
                result[2] if self.embedding_function is not None else None,
            )
            for result in results
        ]
        return docs


    def _select_relevance_score_fn(self) -> Callable[[float], float]:
        """
        The 'correct' relevance function
        may differ depending on a few things, including:
        - the distance / similarity metric used by the VectorStore
        - the scale of your embeddings (OpenAI's are unit normed. Many others are not!)
        - embedding dimensionality
        - etc.
        """
        if self.override_relevance_score_fn is not None:
            return self.override_relevance_score_fn

        # Default strategy is to rely on distance strategy provided
        # in vectorstore constructor
        if self._distance_strategy == DistanceStrategy.COSINE:
            return self._cosine_relevance_score_fn
        elif self._distance_strategy == DistanceStrategy.EUCLIDEAN:
            return self._euclidean_relevance_score_fn
        elif self._distance_strategy == DistanceStrategy.MAX_INNER_PRODUCT:
            return self._max_inner_product_relevance_score_fn
        else:
            raise ValueError(
                "No supported normalization function"
                f" for distance_strategy of {self._distance_strategy}."
                "Consider providing relevance_score_fn to Kinetica constructor."
            )


    @property
    def distance_strategy(self) -> str:
        if self._distance_strategy == DistanceStrategy.EUCLIDEAN:
            return "l2_distance"
        elif self._distance_strategy == DistanceStrategy.COSINE:
            return "cosine_distance"
        elif self._distance_strategy == DistanceStrategy.MAX_INNER_PRODUCT:
            return "dot_product"
        else:
            raise ValueError(
                f"Got unexpected value for distance: {self._distance_strategy}. "
                f"Should be one of {', '.join([ds.value for ds in DistanceStrategy])}."
            )


    def __query_collection(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[Dict[str, str]] = None,
    ) -> List[Any]:
        """Query the collection."""
        # if filter is not None:
        #     filter_clauses = []
        #     for key, value in filter.items():
        #         IN = "in"
        #         if isinstance(value, dict) and IN in map(str.lower, value):
        #             value_case_insensitive = {
        #                 k.lower(): v for k, v in value.items()
        #             }
        #             filter_by_metadata = self.EmbeddingStore.cmetadata[
        #                 key
        #             ].astext.in_(value_case_insensitive[IN])
        #             filter_clauses.append(filter_by_metadata)
        #         else:
        #             filter_by_metadata = self.EmbeddingStore.cmetadata[
        #                 key
        #             ].astext == str(value)
        #             filter_clauses.append(filter_by_metadata)
        
        json_filter = json.dumps(filter) if filter is not None else None
        where_clause = f" where '{json_filter}' = JSON(metadata) " if json_filter is not None else ""

        embedding_str = '[' + ','.join([str(x) for x in embedding]) + ']'
        
        dist_strategy = self.distance_strategy

        query_string = f"""
                SELECT text, metadata, {dist_strategy}(embedding, '{embedding_str}') as distance, embedding
                FROM {self.table_name}
                {where_clause}
                ORDER BY distance asc NULLS LAST
                LIMIT {k}
        """

        self.logger.debug(query_string)
        resp = self._db.execute_sql_and_decode(query_string)
        self.logger.debug(resp)
        return resp


    def max_marginal_relevance_search_with_score_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Return docs selected using the maximal marginal relevance with score
            to embedding vector.

        Maximal marginal relevance optimizes for similarity to query AND diversity
            among selected documents.

        Args:
            embedding: Embedding to look up documents similar to.
            k (int): Number of Documents to return. Defaults to 4.
            fetch_k (int): Number of Documents to fetch to pass to MMR algorithm.
                Defaults to 20.
            lambda_mult (float): Number between 0 and 1 that determines the degree
                of diversity among the results with 0 corresponding
                to maximum diversity and 1 to minimum diversity.
                Defaults to 0.5.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List[Tuple[Document, float]]: List of Documents selected by maximal marginal
                relevance to the query and score for each.
        """
        resp = self.__query_collection(embedding=embedding, k=fetch_k, filter=filter)
        records: OrderedDict = resp["records"]
        results = list(zip(*list(records.values())))

        embedding_list = [struct.unpack('%sf' % self.dimensions, embedding) for embedding in records["embedding"]]

        mmr_selected = maximal_marginal_relevance(
            np.array(embedding, dtype=np.float32),
            embedding_list,
            k=k,
            lambda_mult=lambda_mult,
        )

        candidates = self._results_to_docs_and_scores(results)

        return [r for i, r in enumerate(candidates) if i in mmr_selected]

    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs selected using the maximal marginal relevance.

        Maximal marginal relevance optimizes for similarity to query AND diversity
            among selected documents.

        Args:
            query (str): Text to look up documents similar to.
            k (int): Number of Documents to return. Defaults to 4.
            fetch_k (int): Number of Documents to fetch to pass to MMR algorithm.
                Defaults to 20.
            lambda_mult (float): Number between 0 and 1 that determines the degree
                of diversity among the results with 0 corresponding
                to maximum diversity and 1 to minimum diversity.
                Defaults to 0.5.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List[Document]: List of Documents selected by maximal marginal relevance.
        """
        embedding = self.embedding_function.embed_query(query)
        return self.max_marginal_relevance_search_by_vector(
            embedding,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filter=filter,
            **kwargs,
        )

    def max_marginal_relevance_search_with_score(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[dict] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Return docs selected using the maximal marginal relevance with score.

        Maximal marginal relevance optimizes for similarity to query AND diversity
            among selected documents.

        Args:
            query (str): Text to look up documents similar to.
            k (int): Number of Documents to return. Defaults to 4.
            fetch_k (int): Number of Documents to fetch to pass to MMR algorithm.
                Defaults to 20.
            lambda_mult (float): Number between 0 and 1 that determines the degree
                of diversity among the results with 0 corresponding
                to maximum diversity and 1 to minimum diversity.
                Defaults to 0.5.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List[Tuple[Document, float]]: List of Documents selected by maximal marginal
                relevance to the query and score for each.
        """
        embedding = self.embedding_function.embed_query(query)
        docs = self.max_marginal_relevance_search_with_score_by_vector(
            embedding=embedding,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filter=filter,
            **kwargs,
        )
        return docs

    def max_marginal_relevance_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs selected using the maximal marginal relevance
            to embedding vector.

        Maximal marginal relevance optimizes for similarity to query AND diversity
            among selected documents.

        Args:
            embedding (str): Text to look up documents similar to.
            k (int): Number of Documents to return. Defaults to 4.
            fetch_k (int): Number of Documents to fetch to pass to MMR algorithm.
                Defaults to 20.
            lambda_mult (float): Number between 0 and 1 that determines the degree
                of diversity among the results with 0 corresponding
                to maximum diversity and 1 to minimum diversity.
                Defaults to 0.5.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List[Document]: List of Documents selected by maximal marginal relevance.
        """
        docs_and_scores = self.max_marginal_relevance_search_with_score_by_vector(
            embedding,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filter=filter,
            **kwargs,
        )

        return _results_to_docs(docs_and_scores)

    async def amax_marginal_relevance_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs selected using the maximal marginal relevance."""

        # This is a temporary workaround to make the similarity search
        # asynchronous. The proper solution is to make the similarity search
        # asynchronous in the vector store implementations.
        func = partial(
            self.max_marginal_relevance_search_by_vector,
            embedding,
            k=k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filter=filter,
            **kwargs,
        )
        return await asyncio.get_event_loop().run_in_executor(None, func)

    @classmethod
    def from_texts(
        cls: Type[Kinetica],
        texts: List[str],
        embedding: Embeddings,
        db: GPUdb,
        metadatas: Optional[List[dict]] = None,
        dimensions: int = None,
        collection_name: str = _LANGCHAIN_DEFAULT_COLLECTION_NAME,
        distance_strategy: DistanceStrategy = DEFAULT_DISTANCE_STRATEGY,
        ids: Optional[List[str]] = None,
        pre_delete_collection: bool = False,
        **kwargs: Any,
    ) -> Kinetica:
        """Adds the texts passed in to the vector store and returns it

        Args:
            cls (Type[Kinetica]): Kinetica class
            texts (List[str]): A list of texts for which the embeddings are generated
            embedding (Embeddings): List of embeddings
            db (GPUdb): a GPUdb instance
            metadatas (Optional[List[dict]], optional): List of dicts, JSON describing the texts/documents. Defaults to None.
            dimensions (int, optional): Dimension for the vector data, if not passed a default will be used. Defaults to Dimension.OPENAI.
            collection_name (str, optional): Kinetica schema name. Defaults to _LANGCHAIN_DEFAULT_COLLECTION_NAME.
            distance_strategy (DistanceStrategy, optional): Distance strategy e.g., l2, cosine etc.. Defaults to DEFAULT_DISTANCE_STRATEGY.
            ids (Optional[List[str]], optional): A list of UUIDs for each text/document. Defaults to None.
            pre_delete_collection (bool, optional): Indicates whether the Kinetica schema is to be deleted or not. Defaults to False.

        Returns:
            Kinetica: a `Kinetica` instance
        """
        dimensions = Dimension.OPENAI if dimensions is None or type(dimensions) != int or dimensions <= 0 else dimensions

        embeddings = embedding.embed_documents(list(texts))

        return cls.__from(
            texts=texts,
            embeddings=embeddings,
            embedding=embedding,
            dimensions=dimensions,
            db=db,
            metadatas=metadatas,
            ids=ids,
            collection_name=collection_name,
            distance_strategy=distance_strategy,
            pre_delete_collection=pre_delete_collection,
            **kwargs,
        )


    @classmethod
    def from_embeddings(
        cls: Type[Kinetica],
        text_embeddings: List[Tuple[str, List[float]]],
        embedding: Embeddings,
        db: GPUdb,
        metadatas: Optional[List[dict]] = None,
        dimensions: int = None,
        collection_name: str = _LANGCHAIN_DEFAULT_COLLECTION_NAME,
        distance_strategy: DistanceStrategy = DEFAULT_DISTANCE_STRATEGY,
        ids: Optional[List[str]] = None,
        pre_delete_collection: bool = False,
        **kwargs: Any,
    ) -> Kinetica:
        """Adds the embeddings passed in to the vector store and returns it

        Args:
            cls (Type[Kinetica]): Kinetica class
            texts (List[str]): A list of texts for which the embeddings are generated
            embedding (Embeddings): List of embeddings
            db (GPUdb): a GPUdb instance
            metadatas (Optional[List[dict]], optional): List of dicts, JSON describing the texts/documents. Defaults to None.
            dimensions (int, optional): Dimension for the vector data, if not passed a default will be used. Defaults to Dimension.OPENAI.
            collection_name (str, optional): Kinetica schema name. Defaults to _LANGCHAIN_DEFAULT_COLLECTION_NAME.
            distance_strategy (DistanceStrategy, optional): Distance strategy e.g., l2, cosine etc.. Defaults to DEFAULT_DISTANCE_STRATEGY.
            ids (Optional[List[str]], optional): A list of UUIDs for each text/document. Defaults to None.
            pre_delete_collection (bool, optional): Indicates whether the Kinetica schema is to be deleted or not. Defaults to False.

        Returns:
            Kinetica: a `Kinetica` instance
        """
        dimensions = Dimension.OPENAI if dimensions is None or type(dimensions) != int or dimensions <= 0 else dimensions

        texts = [t[0] for t in text_embeddings]
        embeddings = [t[1] for t in text_embeddings]

        return cls.__from(
            texts=texts,
            embeddings=embeddings,
            embedding=embedding,
            dimensions=dimensions,
            db=db,
            metadatas=metadatas,
            ids=ids,
            collection_name=collection_name,
            distance_strategy=distance_strategy,
            pre_delete_collection=pre_delete_collection,
            **kwargs,
        )

    @classmethod
    def from_documents(
        cls: Type[Kinetica],
        documents: List[Document],
        embedding: Embeddings,
        db: GPUdb,
        metadatas: Optional[List[dict]] = None,
        dimensions: int = None,
        collection_name: str = _LANGCHAIN_DEFAULT_COLLECTION_NAME,
        distance_strategy: DistanceStrategy = DEFAULT_DISTANCE_STRATEGY,
        ids: Optional[List[str]] = None,
        pre_delete_collection: bool = False,
        **kwargs: Any,
    ) -> Kinetica:
        """Adds the list of `Document` passed in to the vector store and returns it

        Args:
            cls (Type[Kinetica]): Kinetica class
            texts (List[str]): A list of texts for which the embeddings are generated
            embedding (Embeddings): List of embeddings
            db (GPUdb): a GPUdb instance
            metadatas (Optional[List[dict]], optional): List of dicts, JSON describing the texts/documents. Defaults to None.
            dimensions (int, optional): Dimension for the vector data, if not passed a default will be used. Defaults to Dimension.OPENAI.
            collection_name (str, optional): Kinetica schema name. Defaults to _LANGCHAIN_DEFAULT_COLLECTION_NAME.
            distance_strategy (DistanceStrategy, optional): Distance strategy e.g., l2, cosine etc.. Defaults to DEFAULT_DISTANCE_STRATEGY.
            ids (Optional[List[str]], optional): A list of UUIDs for each text/document. Defaults to None.
            pre_delete_collection (bool, optional): Indicates whether the Kinetica schema is to be deleted or not. Defaults to False.

        Returns:
            Kinetica: a `Kinetica` instance
        """
        dimensions = Dimension.OPENAI if dimensions is None or type(dimensions) != int or dimensions <= 0 else dimensions

        texts = [d.page_content for d in documents]
        metadatas = [d.metadata for d in documents]

        return cls.from_texts(
            texts=texts,
            embedding=embedding,
            metadatas=metadatas,
            dimensions=dimensions,
            db=db,
            collection_name=collection_name,
            distance_strategy=distance_strategy,
            ids=ids,
            pre_delete_collection=pre_delete_collection,
            **kwargs,
        )
