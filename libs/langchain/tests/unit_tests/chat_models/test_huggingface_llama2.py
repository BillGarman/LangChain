"""Test Hugging Face Llama-2 Chat model."""

from langchain.chat_models.huggingface_llama2 import (
    ChatLlama2Hf,
    InstructionTokens,
    SystemTokens,
)
from langchain.schema.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)


def test_format_messages_as_text_with_system() -> None:
    messages = [
        SystemMessage(content="System Prompt."),
        HumanMessage(content="Human Message."),
        AIMessage(content="AI response."),
        HumanMessage(content="Second Human Message."),
        AIMessage(content="AI response."),
    ]

    assert str(InstructionTokens.B_INST) == "[INST]"
    assert str(InstructionTokens.E_INST) == "[/INST]"
    assert str(SystemTokens.B_SYS) == "<<SYS>>"
    assert str(SystemTokens.E_SYS) == "<</SYS>>"

    ground_truth = (
        "<s>[INST] <<SYS>>\nSystem Prompt.\n<</SYS>>\n\n"
        "Human Message. [/INST] AI response. </s><s>"
        "[INST] Second Human Message. [/INST] "
        "AI response. </s><s>[INST] "
    )

    messages_as_str = ChatLlama2Hf.format_messages_as_text(messages=messages)
    assert messages_as_str == ground_truth, (
        f"Prediction:\n```{messages_as_str}\n" "```\nExpected:\n```{ground_truth}\n```"
    )


def test_format_messages_as_text_without_system() -> None:
    messages = [
        HumanMessage(content="Human Message."),
        AIMessage(content="AI response."),
        HumanMessage(content="Second Human Message."),
        AIMessage(content="Second AI response."),
    ]

    assert str(InstructionTokens.B_INST) == "[INST]"
    assert str(InstructionTokens.E_INST) == "[/INST]"
    assert str(SystemTokens.B_SYS) == "<<SYS>>"
    assert str(SystemTokens.E_SYS) == "<</SYS>>"

    ground_truth = (
        "<s>[INST] Human Message. [/INST] "
        "AI response. </s><s>[INST] "
        "Second Human Message. [/INST] "
        "Second AI response. </s><s>[INST] "
    )

    messages_as_str = ChatLlama2Hf.format_messages_as_text(messages=messages)
    assert messages_as_str == ground_truth, (
        f"Prediction:\n```{messages_as_str}\n" "```\nExpected:\n```{ground_truth}\n```"
    )
