"""Test Anthropic API wrapper."""
from typing import List

import pytest

from langchain.callbacks.manager import CallbackManager
from langchain.chat_models.anthropic import (
    ChatAnthropic,
    convert_messages_to_prompt_anthropic,
)
from langchain.schema import ChatGeneration, LLMResult
from langchain.schema.messages import AIMessage, BaseMessage, HumanMessage
from tests.unit_tests.callbacks.fake_callback_handler import FakeCallbackHandler


def test_anthropic_call() -> None:
    """Test valid call to anthropic."""
    chat = ChatAnthropic(model="test")
    message = HumanMessage(content="Hello")
    response = chat([message])
    assert isinstance(response, AIMessage)
    assert isinstance(response.content, str)


def test_anthropic_generate() -> None:
    """Test generate method of anthropic."""
    chat = ChatAnthropic(model="test")
    chat_messages: List[List[BaseMessage]] = [
        [HumanMessage(content="How many toes do dogs have?")]
    ]
    messages_copy = [messages.copy() for messages in chat_messages]
    result: LLMResult = chat.generate(chat_messages)
    assert isinstance(result, LLMResult)
    for response in result.generations[0]:
        assert isinstance(response, ChatGeneration)
        assert isinstance(response.text, str)
        assert response.text == response.message.content
    assert chat_messages == messages_copy


def test_anthropic_streaming() -> None:
    """Test streaming tokens from anthropic."""
    chat = ChatAnthropic(model="test", streaming=True)
    message = HumanMessage(content="Hello")
    response = chat([message])
    assert isinstance(response, AIMessage)
    assert isinstance(response.content, str)


def test_anthropic_streaming_callback() -> None:
    """Test that streaming correctly invokes on_llm_new_token callback."""
    callback_handler = FakeCallbackHandler()
    callback_manager = CallbackManager([callback_handler])
    chat = ChatAnthropic(
        model="test",
        streaming=True,
        callback_manager=callback_manager,
        verbose=True,
    )
    message = HumanMessage(content="Write me a sentence with 10 words.")
    chat([message])
    assert callback_handler.llm_streams > 1


@pytest.mark.asyncio
async def test_anthropic_async_streaming_callback() -> None:
    """Test that streaming correctly invokes on_llm_new_token callback."""
    callback_handler = FakeCallbackHandler()
    callback_manager = CallbackManager([callback_handler])
    chat = ChatAnthropic(
        model="test",
        streaming=True,
        callback_manager=callback_manager,
        verbose=True,
    )
    chat_messages: List[BaseMessage] = [
        HumanMessage(content="How many toes do dogs have?")
    ]
    result: LLMResult = await chat.agenerate([chat_messages])
    assert callback_handler.llm_streams > 1
    assert isinstance(result, LLMResult)
    for response in result.generations[0]:
        assert isinstance(response, ChatGeneration)
        assert isinstance(response.text, str)
        assert response.text == response.message.content


def test_formatting() -> None:
    messages: List[BaseMessage] = [HumanMessage(content="Hello")]
    result = convert_messages_to_prompt_anthropic(messages)
    assert result == "\n\nHuman: Hello\n\nAssistant:"

    messages = [HumanMessage(content="Hello"), AIMessage(content="Answer:")]
    result = convert_messages_to_prompt_anthropic(messages)
    assert result == "\n\nHuman: Hello\n\nAssistant: Answer:"


def test_anthropic_model_kwargs() -> None:
    llm = ChatAnthropic(model_kwargs={"foo": "bar"})
    assert llm.model_kwargs == {"foo": "bar"}


def test_anthropic_invalid_model_kwargs() -> None:
    with pytest.raises(ValueError):
        ChatAnthropic(model_kwargs={"max_tokens_to_sample": 5})


def test_anthropic_incorrect_field() -> None:
    with pytest.warns(match="not default parameter"):
        llm = ChatAnthropic(foo="bar")
    assert llm.model_kwargs == {"foo": "bar"}
