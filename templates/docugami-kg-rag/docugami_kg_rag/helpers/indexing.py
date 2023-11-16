import os
from pathlib import Path
import pickle

from langchain.document_loaders import DocugamiLoader
from langchain.schema import Document
from langchain.storage.in_memory import InMemoryStore
from langchain.vectorstores.pinecone import Pinecone
import pinecone
from typing import Dict, List

from docugami_kg_rag.config import (
    EMBEDDINGS,
    EMBEDDINGS_DIMENSIONS,
    INCLUDE_XML_TAGS,
    INDEXING_LOCAL_STATE_PATH,
    MIN_CHUNK_TEXT_LENGTH,
    PARENT_HIERARCHY_LEVELS,
    PINECONE_INDEX,
    SUB_CHUNK_TABLES,
    LocalIndexState,
)
from docugami_kg_rag.helpers.documents import get_parent_id_mappings
from docugami_kg_rag.helpers.retrieval import docset_name_to_retriever_tool_function_name, chunks_to_retriever_tool_description


def read_all_local_index_state() -> Dict[str, LocalIndexState]:
    if not Path(INDEXING_LOCAL_STATE_PATH).is_file():
        return {}  # not found

    with open(INDEXING_LOCAL_STATE_PATH, "rb") as file:
        return pickle.load(file)


def update_local_index(docset_id: str, name: str, chunks: List[Document]):
    # Populate local index

    state = read_all_local_index_state()

    parents = get_parent_id_mappings(chunks)
    parents_by_id = InMemoryStore()
    parents_by_id.mset(parents.items())

    tool_function_name = docset_name_to_retriever_tool_function_name(name)
    tool_description = chunks_to_retriever_tool_description(name, chunks)

    docset_state = LocalIndexState(
        parents_by_id=parents_by_id,
        retrieval_tool_function_name=tool_function_name,
        retrieval_tool_description=tool_description,
    )
    print(docset_state)
    state[docset_id] = docset_state

    # Serialize state to disk (Deserialized in chain)
    store_local_path = Path(INDEXING_LOCAL_STATE_PATH)
    os.makedirs(os.path.dirname(store_local_path), exist_ok=True)
    with open(store_local_path, "wb") as file:
        pickle.dump(state, file)


def populate_pinecode_index(index_name: str, chunks: List[Document]):
    # Populate pinecone with the given chunks

    if index_name not in pinecone.list_indexes():
        # Create index if it does not exist
        print(f"Creating pinecone index {index_name}...")
        pinecone.create_index(name=index_name, dimension=EMBEDDINGS_DIMENSIONS)

        print(f"Done creating pinecone index {index_name}, now embedding...")
        Pinecone.from_documents(
            documents=chunks,
            embedding=EMBEDDINGS,
            index_name=index_name,
        )

        print(f"Done embedding documents to pinecode index {index_name}!")
    else:
        raise Exception(f"Index {index_name} already exists. Please delete it to re-index, or you will get duplicate chunks.")


def index_docset(docset_id: str, name: str):
    # Indexes the given docset

    print(f"Indexing {name} (ID: {docset_id})")

    loader = DocugamiLoader(
        docset_id=docset_id,
        min_text_length=MIN_CHUNK_TEXT_LENGTH,
        sub_chunk_tables=SUB_CHUNK_TABLES,
        include_xml_tags=INCLUDE_XML_TAGS,
        parent_hierarchy_levels=PARENT_HIERARCHY_LEVELS,
        include_project_metadata_in_doc_metadata=False,  # not used, so lighten the vector index
    )

    chunks = loader.load()
    docset_pinecone_index_name = f"{PINECONE_INDEX}-{docset_id}"
    populate_pinecode_index(docset_pinecone_index_name, chunks)
    update_local_index(docset_id, name, chunks)
