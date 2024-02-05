"""Test Groq Chat API wrapper."""

import json
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import langchain_core.load as lc_load
import pytest
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)

from langchain_community.chat_models.groq import ChatGroq, _convert_dict_to_message

os.environ["GROQ_API_KEY"] = "fake-key"


@pytest.mark.requires("groq")
def test_groq_model_param() -> None:
    llm = ChatGroq(model="foo")
    assert llm.model_name == "foo"
    llm = ChatGroq(model_name="foo")
    assert llm.model_name == "foo"


def test_function_message_dict_to_function_message() -> None:
    content = json.dumps({"result": "Example #1"})
    name = "test_function"
    result = _convert_dict_to_message(
        {
            "role": "function",
            "name": name,
            "content": content,
        }
    )
    assert isinstance(result, FunctionMessage)
    assert result.name == name
    assert result.content == content


def test__convert_dict_to_message_human() -> None:
    message = {"role": "user", "content": "foo"}
    result = _convert_dict_to_message(message)
    expected_output = HumanMessage(content="foo")
    assert result == expected_output


def test__convert_dict_to_message_ai() -> None:
    message = {"role": "assistant", "content": "foo"}
    result = _convert_dict_to_message(message)
    expected_output = AIMessage(content="foo")
    assert result == expected_output


def test__convert_dict_to_message_system() -> None:
    message = {"role": "system", "content": "foo"}
    result = _convert_dict_to_message(message)
    expected_output = SystemMessage(content="foo")
    assert result == expected_output


@pytest.fixture
def mock_completion() -> dict:
    return {
        "id": "chatcmpl-7fcZavknQda3SQ",
        "object": "chat.completion",
        "created": 1689989000,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Bar Baz",
                },
                "finish_reason": "stop",
            }
        ],
    }


def test_groq_invoke(mock_completion: dict) -> None:
    llm = ChatGroq()
    mock_client = MagicMock()
    completed = False

    def mock_create(*args: Any, **kwargs: Any) -> Any:
        nonlocal completed
        completed = True
        return mock_completion

    mock_client.create = mock_create
    with patch.object(
        llm,
        "client",
        mock_client,
    ):
        res = llm.invoke("bar")
        assert res.content == "Bar Baz"
        assert type(res) == AIMessage
    assert completed


async def test_groq_ainvoke(mock_completion: dict) -> None:
    llm = ChatGroq()
    mock_client = AsyncMock()
    completed = False

    async def mock_create(*args: Any, **kwargs: Any) -> Any:
        nonlocal completed
        completed = True
        return mock_completion

    mock_client.create = mock_create
    with patch.object(
        llm,
        "async_client",
        mock_client,
    ):
        res = await llm.ainvoke("bar")
        assert res.content == "Bar Baz"
        assert type(res) == AIMessage
    assert completed


def test_chat_groq_extra_kwargs() -> None:
    """Test extra kwargs to chat groq."""
    # Check that foo is saved in extra_kwargs.
    with pytest.warns(UserWarning) as record:
        llm = ChatGroq(foo=3, max_tokens=10)
        assert llm.max_tokens == 10
        assert llm.model_kwargs == {"foo": 3}
    assert len(record) == 1
    assert "foo is not default parameter" in record[0].message.args[0]

    # Test that if extra_kwargs are provided, they are added to it.
    with pytest.warns(UserWarning) as record:
        llm = ChatGroq(foo=3, model_kwargs={"bar": 2})
        assert llm.model_kwargs == {"foo": 3, "bar": 2}
    assert len(record) == 1
    assert "foo is not default parameter" in record[0].message.args[0]

    # Test that if provided twice it errors
    with pytest.raises(ValueError):
        ChatGroq(foo=3, model_kwargs={"foo": 2})

    # Test that if explicit param is specified in kwargs it errors
    with pytest.raises(ValueError):
        ChatGroq(model_kwargs={"temperature": 0.2})

    # Test that "model" cannot be specified in kwargs
    with pytest.raises(ValueError):
        ChatGroq(model_kwargs={"model": "test-model"})


def test_chat_groq_invalid_streaming_params() -> None:
    """Test that an error is raised if streaming is invoked with n>1."""
    with pytest.raises(ValueError):
        ChatGroq(
            max_tokens=10,
            streaming=True,
            temperature=0,
            n=5,
        )


def test_chat_groq_secret() -> None:
    """Test that secret is not printed"""
    secret = "secretKey"
    not_secret = "safe"
    llm = ChatGroq(api_key=secret, model_kwargs={"not_secret": not_secret})
    stringified = str(llm)
    assert not_secret in stringified
    assert secret not in stringified


@pytest.mark.filterwarnings("ignore:The function `loads` is in beta")
def test_groq_serialization() -> None:
    """Test that ChatGroq can be successfully serialized and deserialized"""
    llm = ChatGroq(groq_api_key="top secret", temperature=0.5)
    llm2 = lc_load.loads(lc_load.dumps(llm))
    assert type(llm2) is ChatGroq

    # Secrets are not serialized and should be reread from the environment.
    assert llm.groq_api_key.get_secret_value() != llm2.groq_api_key.get_secret_value()
    assert llm2.groq_api_key.get_secret_value() == os.environ["GROQ_API_KEY"]
    # Non-secret field was serialized
    assert llm.temperature == llm2.temperature
    # Empty field is still empty
    assert llm.groq_api_base == llm2.groq_api_base
