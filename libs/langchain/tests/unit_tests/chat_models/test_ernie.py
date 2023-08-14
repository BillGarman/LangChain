from langchain.schema.messages import HumanMessage, AIMessage, SystemMessage
from langchain.chat_models.ernie import _convert_message_to_dict


def test__convert_dict_to_message_human() -> None:
    message = HumanMessage(content="foo")
    result = _convert_message_to_dict(message)
    expected_output = {"role":"user", "content":"foo"}
    assert result == expected_output


def test__convert_dict_to_message_ai() -> None:
    message = AIMessage(content="foo")
    result = _convert_message_to_dict(message)
    expected_output = {"role":"assistant", "content":"foo"}
    assert result == expected_output

def test__convert_dict_to_message_system() -> None:
    message = SystemMessage(content="foo")
    result = _convert_message_to_dict(message)
    expected_output = {"role":"system", "content":"foo"}
    assert result == expected_output
