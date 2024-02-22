"""Test BigDL LLM"""
from langchain_core.outputs import LLMResult

from langchain_community.llms.bigdl import BigdlLLM

def test_call() -> None:
    """Test valid call to baichuan."""
    llm = BigdlLLM.from_model_id(
        model_id="lmsys/vicuna-7b-v1.5",
        model_kwargs={"temperature": 0, "max_length": 16, "trust_remote_code": True})
    output = llm("Hello!")
    assert isinstance(output, str)


def test_generate() -> None:
    """Test valid call to baichuan."""
    llm = BigdlLLM.from_model_id(
        model_id="lmsys/vicuna-7b-v1.5",
        model_kwargs={"temperature": 0, "max_length": 16, "trust_remote_code": True})
    output = llm.generate(["Hello!"])
    assert isinstance(output, LLMResult)
    assert isinstance(output.generations, list)
