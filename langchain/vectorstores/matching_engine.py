"""Vertex Matching Engine implementation of the vector store."""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Type

from langchain.docstore.document import Document
from langchain.embeddings import TensorflowHubEmbeddings
from langchain.embeddings.base import Embeddings
from langchain.vectorstores.base import VectorStore

if TYPE_CHECKING:
    from google.cloud import firestore
    from google.cloud import storage
    from google.cloud.aiplatform import MatchingEngineIndex, MatchingEngineIndexEndpoint
    from google.oauth2.service_account import Credentials

logger = logging.getLogger()


class MatchingEngine(VectorStore):
    """Vertex Matching Engine implementation of the vector store.

    While the embeddings are stored in the Matching Engine, the embedded
    documents will be stored either in GCS or Firestore.

    An existing Index and corresponding Endpoint are preconditions for
    using this module.

    See usage in docs/modules/indexes/vectorstores/examples/matchingengine.ipynb

    Note that this implementation is mostly meant for reading if you are
    planning to do a real time implementation. While reading is a real time
    operation, updating the index takes close to one hour."""

    def __init__(
        self,
        project_id: str,
        index: MatchingEngineIndex,
        endpoint: MatchingEngineIndexEndpoint,
        embedding: Embeddings,
        gcs_client: Optional[storage.Client] = None,
        firestore_client: Optional[firestore.Client] = None,
        gcs_bucket_name: Optional[str] = None,
        firestore_collection_name: Optional[str] = None,
        credentials: Optional[Credentials] = None,
    ):
        """Vertex Matching Engine implementation of the vector store.

        While the embeddings are stored in the Matching Engine, the embedded
        documents will be stored either in GCS or Firestore. Note that the
        Firestore collection must have a field "content" which holds the
        text content of the document.

        An existing Index and corresponding Endpoint are preconditions for
        using this module.

        See usage in
        docs/modules/indexes/vectorstores/examples/matchingengine.ipynb.

        Note that this implementation is mostly meant for reading if you are
        planning to do a real time implementation. While reading is a real time
        operation, updating the index takes close to one hour.

        Attributes:
            project_id: The GCS project id.
            index: The created index class. See
                ~:func:`MatchingEngine.from_components`.
            endpoint: The created endpoint class. See
                ~:func:`MatchingEngine.from_components`.
            embedding: A :class:`Embeddings` that will be used for
                embedding the text sent. If none is sent, then the
                multilingual Tensorflow Universal Sentence Encoder will be used.
            gcs_client: The GCS client.
            gcs_bucket_name: The GCS bucket name.
            firestore_client: The Firestore client.
            firestore_collection_name: The Firestore collection name 
            credentials (Optional): Created GCP credentials.
        """
        super().__init__()
        self._validate_google_libraries_installation()

        self.project_id = project_id
        self.index = index
        self.endpoint = endpoint
        self.embedding = embedding
        self.credentials = credentials
        self.gcs_client = gcs_client
        self.gcs_bucket_name = gcs_bucket_name
        self.firestore_client = firestore_client
        self.firestore_collection_name = firestore_collection_name
        if not (firestore_collection_name or gcs_bucket_name):
            raise ValueError("Storage not specified. Either a firestore collection or gcs bucket must be provided!")

    def _validate_google_libraries_installation(self) -> None:
        """Validates that Google libraries that are needed are installed."""
        try:
            from google.cloud import aiplatform, storage  # noqa: F401
            from google.oauth2 import service_account  # noqa: F401
            from google.cloud import firestore
        except ImportError:
            raise ImportError(
                "You must run `pip install --upgrade "
                "google-cloud-aiplatform google-cloud-storage google-cloud-firestore`"
                "to use the MatchingEngine Vectorstore."
            )

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Run more texts through the embeddings and add to the vectorstore.

        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas associated with the texts. This metadata is stored as fields in firestore if specified.
            kwargs: vectorstore specific parameters.

        Returns:
            List of ids from adding the texts into the vectorstore.
        """
        logger.debug("Embedding documents.")
        embeddings = self.embedding.embed_documents(list(texts))
        jsons = []
        ids = []
        # Could be improved with async.
        if self.firestore_client:
            for i, (embedding, text) in enumerate(zip(embeddings, texts)):
                id = str(uuid.uuid4())
                ids.append(id)
                jsons.append({"id": id, "embedding": embedding})
                if metadatas:
                    self._upload_to_firestore(text, id, metadatas[i])
                else:
                    self._upload_to_firestore(text, id)

            logger.debug(f"Uploaded {len(ids)} documents to Firestore.")
        
        else:
            for embedding, text in zip(embeddings, texts):
                id = str(uuid.uuid4())
                ids.append(id)
                jsons.append({"id": id, "embedding": embedding})
                self._upload_to_gcs(text, f"documents/{id}")

            logger.debug(f"Uploaded {len(ids)} documents to GCS.")

        # Creating json lines from the embedded documents.
        result_str = "\n".join([json.dumps(x) for x in jsons])

        filename_prefix = f"indexes/{uuid.uuid4()}"
        filename = f"{filename_prefix}/{time.time()}.json"
        if not self.gcs_client:
            raise ValueError("For indexing new data and updating the matching engine, a gcs client or bucket name must be supplied upon initalization!")
        self._upload_to_gcs(result_str, filename)
        logger.debug(
            f"Uploaded updated json with embeddings to "
            f"{self.gcs_bucket_name}/{filename}."
        )

        self.index = self.index.update_embeddings(
            contents_delta_uri=f"gs://{self.gcs_bucket_name}/{filename_prefix}/"
        )

        logger.debug("Updated index with new configuration.")

        return ids
    
    def _upload_to_gcs(self, data: str, gcs_location: str) -> None:
        """Uploads data to gcs_location.

        Args:
            data: The data that will be stored.
            gcs_location: The location where the data will be stored.
        """
        bucket = self.gcs_client.get_bucket(self.gcs_bucket_name)
        blob = bucket.blob(gcs_location)
        blob.upload_from_string(data)

    def _upload_to_firestore(self, data: str, id, metadata: Optional[dict]) -> None:
        """Uploads data to firestore_collection.

        Args:
            data: The data that will be stored.
            id: The id for the data record.
        """
        data_load = {
            'content': data,
            
        }
        data_load.update(metadata)
        self.firestore_client.collection(self.firestore_collection_name).document(id).set(data_load)
        
    def similarity_search(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> List[Document]:
        """Return docs most similar to query.

        Args:
            query: The string that will be used to search for similar documents.
            k: The amount of neighbors that will be retrieved.

        Returns:
            A list of k matching documents.
        """

        logger.debug(f"Embedding query {query}.")
        embedding_query = self.embedding.embed_documents([query])

        response = self.endpoint.match(
            deployed_index_id=self._get_index_id(),
            queries=embedding_query,
            num_neighbors=k,
        )

        if len(response) == 0:
            return []

        logger.debug(f"Found {len(response)} matches for the query {query}.")

        results = []

        # I'm only getting the first one because queries receives an array
        # and the similarity_search method only recevies one query. This
        # means that the match method will always return an array with only
        # one element.
        if self.gcs_client:
            for doc in response[0]:
                page_content = self._download_from_gcs(f"documents/{doc.id}")
                results.append(Document(page_content=page_content))
        else:
            for doc in response[0]:
                page = self.firestore_client.collection(self.firestore_collection_name).document(doc.id).get().to_dict()
                metadata = {"id": doc.id}
                metadata.update({key: value for key, value in page.items() if key!='content'})
                results.append(Document(page_content=page['content'], metadata=metadata))

        logger.debug("Downloaded documents for query.")

        return results

    def _get_index_id(self) -> str:
        """Gets the correct index id for the endpoint.

        Returns:
            The index id if found (which should be found) or throws
            ValueError otherwise.
        """
        for index in self.endpoint.deployed_indexes:
            if index.index == self.index.resource_name:
                return index.id

        raise ValueError(
            f"No index with id {self.index.resource_name} "
            f"deployed on endpoint "
            f"{self.endpoint.display_name}."
        )

    def _download_from_gcs(self, gcs_location: str) -> str:
        """Downloads from GCS in text format.

        Args:
            gcs_location: The location where the file is located.

        Returns:
            The string contents of the file.
        """
        bucket = self.gcs_client.get_bucket(self.gcs_bucket_name)
        blob = bucket.blob(gcs_location)
        return blob.download_as_string()

    @classmethod
    def from_texts(
        cls: Type["MatchingEngine"],
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> "MatchingEngine":
        """Use from components instead."""
        raise NotImplementedError(
            "This method is not implemented. Instead, you should initialize the class"
            " with `MatchingEngine.from_components(...)` and then call "
            "`add_texts`"
        )

    @classmethod
    def from_components(
        cls: Type["MatchingEngine"],
        project_id: str,
        region: str,
        index_id: str,
        endpoint_id: str,
        gcs_bucket_name: Optional[str] = None,
        firestore_collection_name: Optional[str] = None,
        credentials_path: Optional[str] = None,
        embedding: Optional[Embeddings] = None,
    ) -> "MatchingEngine":
        """Takes the object creation out of the constructor.

        Args:
            project_id: The GCP project id.
            region: The default location making the API calls. It must have
            the same location as the GCS bucket and must be regional.
            gcs_bucket_name: The location where the vectors will be stored in
            order for the index to be created.
            index_id: The id of the created index.
            endpoint_id: The id of the created endpoint.
            credentials_path: (Optional) The path of the Google credentials on
            the local file system.
            embedding: The :class:`Embeddings` that will be used for
            embedding the texts.

        Returns:
            A configured MatchingEngine with the texts added to the index.
        """
        credentials = cls._create_credentials_from_file(credentials_path)
        index = cls._create_index_by_id(index_id, project_id, region, credentials)
        endpoint = cls._create_endpoint_by_id(
            endpoint_id, project_id, region, credentials
        )
        if gcs_bucket_name:
            gcs_bucket_name = cls._validate_gcs_bucket(gcs_bucket_name)
            gcs_client = cls._get_gcs_client(credentials, project_id)
            firestore_client = None
        elif firestore_collection_name:
            firestore_client = cls._get_firestore_client(credentials, project_id)
            gcs_client = None
        else:
            raise ValueError("Either gcs_bucket_name or firestore_collection_name must be provided!")
            
        cls._init_aiplatform(project_id, region, gcs_bucket_name, credentials)

        return cls(
            project_id=project_id,
            index=index,
            endpoint=endpoint,
            embedding=embedding or cls._get_default_embeddings(),
            gcs_client=gcs_client,
            firestore_client = firestore_client,
            credentials=credentials,
            gcs_bucket_name=gcs_bucket_name,
            firestore_collection_name=firestore_collection_name
        )

    @classmethod
    def _validate_gcs_bucket(cls, gcs_bucket_name: str) -> str:
        """Validates the gcs_bucket_name as a bucket name.

        Args:
              gcs_bucket_name: The received bucket uri.

        Returns:
              A valid gcs_bucket_name or throws ValueError if full path is
              provided.
        """
        gcs_bucket_name = gcs_bucket_name.replace("gs://", "")
        if "/" in gcs_bucket_name:
            raise ValueError(
                f"The argument gcs_bucket_name should only be "
                f"the bucket name. Received {gcs_bucket_name}"
            )
        return gcs_bucket_name

    @classmethod
    def _create_credentials_from_file(
        cls, json_credentials_path: Optional[str]
    ) -> Optional[Credentials]:
        """Creates credentials for GCP.

        Args:
             json_credentials_path: The path on the file system where the
             credentials are stored.

         Returns:
             An optional of Credentials or None, in which case the default
             will be used.
        """

        from google.oauth2 import service_account

        credentials = None
        if json_credentials_path is not None:
            credentials = service_account.Credentials.from_service_account_file(
                json_credentials_path
            )

        return credentials

    @classmethod
    def _create_index_by_id(
        cls, index_id: str, project_id: str, region: str, credentials: "Credentials"
    ) -> MatchingEngineIndex:
        """Creates a MatchingEngineIndex object by id.

        Args:
            index_id: The created index id.
            project_id: The project to retrieve index from.
            region: Location to retrieve index from.
            credentials: GCS credentials.

        Returns:
            A configured MatchingEngineIndex.
        """

        from google.cloud import aiplatform

        logger.debug(f"Creating matching engine index with id {index_id}.")
        return aiplatform.MatchingEngineIndex(
            index_name=index_id,
            project=project_id,
            location=region,
            credentials=credentials,
        )

    @classmethod
    def _create_endpoint_by_id(
        cls, endpoint_id: str, project_id: str, region: str, credentials: "Credentials"
    ) -> MatchingEngineIndexEndpoint:
        """Creates a MatchingEngineIndexEndpoint object by id.

        Args:
            endpoint_id: The created endpoint id.
            project_id: The project to retrieve index from.
            region: Location to retrieve index from.
            credentials: GCS credentials.

        Returns:
            A configured MatchingEngineIndexEndpoint.
        """

        from google.cloud import aiplatform

        logger.debug(f"Creating endpoint with id {endpoint_id}.")
        return aiplatform.MatchingEngineIndexEndpoint(
            index_endpoint_name=endpoint_id,
            project=project_id,
            location=region,
            credentials=credentials,
        )

    @classmethod
    def _get_gcs_client(
        cls, credentials: "Credentials", project_id: str
    ) -> "storage.Client":
        """Lazily creates a GCS client.

        Returns:
            A configured GCS client.
        """

        from google.cloud import storage

        return storage.Client(credentials=credentials, project=project_id)

    @classmethod
    def _get_firestore_client(
        cls, credentials: "Credentials", project_id: str
    ) -> "firestore.Client":
        """Lazily creates a Firestore client.

        Returns:
            A configured Firestore client.
        """

        from google.cloud import firestore

        return firestore.Client(credentials=credentials)
    
    @classmethod
    def _init_aiplatform(
        cls,
        project_id: str,
        region: str,
        gcs_bucket_name: str,
        credentials: "Credentials",
    ) -> None:
        """Configures the aiplatform library.

        Args:
            project_id: The GCP project id.
            region: The default location making the API calls. It must have
            the same location as the GCS bucket and must be regional.
            gcs_bucket_name: GCS staging location.
            credentials: The GCS Credentials object.
        """

        from google.cloud import aiplatform

        logger.debug(
            f"Initializing AI Platform for project {project_id} on "
            f"{region} and for {gcs_bucket_name}."
        )
        aiplatform.init(
            project=project_id,
            location=region,
            staging_bucket=gcs_bucket_name,
            credentials=credentials,
        )

    @classmethod
    def _get_default_embeddings(cls) -> TensorflowHubEmbeddings:
        """This function returns the default embedding.

        Returns:
            Default TensorflowHubEmbeddings to use.
        """
        return TensorflowHubEmbeddings()
