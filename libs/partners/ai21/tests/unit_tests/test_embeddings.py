"""Test embedding model integration."""
import os
from unittest.mock import Mock

import pytest
from ai21 import AI21Client
from ai21.models import EmbedResult, EmbedResponse, EmbedType
from pytest_mock import MockerFixture

from langchain_ai21.embeddings import AI21Embeddings


_EXAMPLE_EMBEDDING_0 = [1.0, 2.0, 3.0]
_EXAMPLE_EMBEDDING_1 = [4.0, 5.0, 6.0]
_EXAMPLE_EMBEDDING_2 = [7.0, 8.0, 9.0]

_EXAMPLE_EMBEDDING_RESPONSE = EmbedResponse(
    results=[
        EmbedResult(_EXAMPLE_EMBEDDING_0),
        EmbedResult(_EXAMPLE_EMBEDDING_1),
        EmbedResult(_EXAMPLE_EMBEDDING_2),
    ],
    id="test_id",
)


@pytest.mark.requires("ai21")
@pytest.fixture
def mock_client_with_embeddings(mocker: MockerFixture) -> Mock:
    mock_client = mocker.MagicMock(spec=AI21Client)
    mock_client.embed = mocker.MagicMock()
    mock_client.embed.create.return_value = _EXAMPLE_EMBEDDING_RESPONSE

    return mock_client


@pytest.mark.requires("ai21")
def test_embed_query(mock_client_with_embeddings: Mock) -> None:
    llm = AI21Embeddings(client=mock_client_with_embeddings, api_key="test_key")

    text = "Hello embeddings world!"
    response = llm.embed_query(text=text)
    assert response == _EXAMPLE_EMBEDDING_0
    mock_client_with_embeddings.embed.create.assert_called_once_with(
        texts=[text],
        type=EmbedType.QUERY,
    )


@pytest.mark.requires("ai21")
def test_embed_documents(mock_client_with_embeddings: Mock) -> None:
    llm = AI21Embeddings(client=mock_client_with_embeddings, api_key="test_key")

    texts = ["Hello embeddings world!", "Some other text", "Some more text"]
    response = llm.embed_documents(texts=texts)
    assert response == [_EXAMPLE_EMBEDDING_0, _EXAMPLE_EMBEDDING_1, _EXAMPLE_EMBEDDING_2]
    mock_client_with_embeddings.embed.create.assert_called_once_with(
        texts=texts,
        type=EmbedType.QUERY,
    )
