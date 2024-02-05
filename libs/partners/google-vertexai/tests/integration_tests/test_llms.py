"""Test Vertex AI API wrapper.

Your end-user credentials would be used to make the calls (make sure you've run 
`gcloud auth login` first).
"""
import os
from typing import Optional

import pytest
from langchain_core.outputs import LLMResult

from langchain_google_vertexai.llms import VertexAI, VertexAIModelGarden

model_names_to_test = ["text-bison@001", "gemini-pro"]
model_names_to_test_with_default = [None] + model_names_to_test


@pytest.mark.parametrize(
    "model_name",
    model_names_to_test_with_default,
)
def test_vertex_initialization(model_name: str) -> None:
    llm = VertexAI(model_name=model_name) if model_name else VertexAI()
    assert llm._llm_type == "vertexai"
    try:
        assert llm.model_name == llm.client._model_id
    except AttributeError:
        assert llm.model_name == llm.client._model_name.split("/")[-1]


@pytest.mark.parametrize(
    "model_name",
    model_names_to_test_with_default,
)
def test_vertex_invoke(model_name: str) -> None:
    llm = (
        VertexAI(model_name=model_name, temperature=0)
        if model_name
        else VertexAI(temperature=0.0)
    )
    output = llm.invoke("Say foo:")
    assert isinstance(output, str)


@pytest.mark.parametrize(
    "model_name",
    model_names_to_test_with_default,
)
def test_vertex_generate(model_name: str) -> None:
    llm = (
        VertexAI(model_name=model_name, temperature=0)
        if model_name
        else VertexAI(temperature=0.0)
    )
    output = llm.generate(["Say foo:"])
    assert isinstance(output, LLMResult)
    assert len(output.generations) == 1


@pytest.mark.xfail(reason="VertexAI doesn't always respect number of candidates")
def test_vertex_generate_multiple_candidates() -> None:
    llm = VertexAI(temperature=0.3, n=2, model_name="text-bison@001")
    output = llm.generate(["Say foo:"])
    assert isinstance(output, LLMResult)
    assert len(output.generations) == 1
    assert len(output.generations[0]) == 2


@pytest.mark.xfail(reason="VertexAI doesn't always respect number of candidates")
def test_vertex_generate_code() -> None:
    llm = VertexAI(temperature=0.3, n=2, model_name="code-bison@001")
    output = llm.generate(["generate a python method that says foo:"])
    assert isinstance(output, LLMResult)
    assert len(output.generations) == 1
    assert len(output.generations[0]) == 2


async def test_vertex_agenerate() -> None:
    llm = VertexAI(temperature=0)
    output = await llm.agenerate(["Please say foo:"])
    assert isinstance(output, LLMResult)


@pytest.mark.parametrize(
    "model_name",
    model_names_to_test_with_default,
)
def test_stream(model_name: str) -> None:
    llm = (
        VertexAI(temperature=0, model_name=model_name)
        if model_name
        else VertexAI(temperature=0)
    )
    for token in llm.stream("I'm Pickle Rick"):
        assert isinstance(token, str)


@pytest.mark.parametrize(
    "model_name",
    model_names_to_test_with_default,
)
async def test_astream(model_name: str) -> None:
    llm = (
        VertexAI(temperature=0, model_name=model_name)
        if model_name
        else VertexAI(temperature=0)
    )
    async for token in llm.astream("I'm Pickle Rick"):
        assert isinstance(token, str)


async def test_vertex_consistency() -> None:
    llm = VertexAI(temperature=0)
    output = llm.generate(["Please say foo:"])
    streaming_output = llm.generate(["Please say foo:"], stream=True)
    async_output = await llm.agenerate(["Please say foo:"])
    async_streaming_output = await llm.agenerate(["Please say foo:"], stream=True)
    assert output.generations[0][0].text == streaming_output.generations[0][0].text
    assert output.generations[0][0].text == async_output.generations[0][0].text
    assert (
        output.generations[0][0].text == async_streaming_output.generations[0][0].text
    )


@pytest.mark.skip("CI testing not set up")
@pytest.mark.parametrize(
    "endpoint_os_variable_name,result_arg",
    [("FALCON_ENDPOINT_ID", "generated_text"), ("LLAMA_ENDPOINT_ID", None)],
)
def test_model_garden(
    endpoint_os_variable_name: str, result_arg: Optional[str]
) -> None:
    """In order to run this test, you should provide endpoint names.

    Example:
    export FALCON_ENDPOINT_ID=...
    export LLAMA_ENDPOINT_ID=...
    export PROJECT=...
    """
    endpoint_id = os.environ[endpoint_os_variable_name]
    project = os.environ["PROJECT"]
    location = "europe-west4"
    llm = VertexAIModelGarden(
        endpoint_id=endpoint_id,
        project=project,
        result_arg=result_arg,
        location=location,
    )
    output = llm("What is the meaning of life?")
    assert isinstance(output, str)
    assert llm._llm_type == "vertexai_model_garden"


@pytest.mark.skip("CI testing not set up")
@pytest.mark.parametrize(
    "endpoint_os_variable_name,result_arg",
    [("FALCON_ENDPOINT_ID", "generated_text"), ("LLAMA_ENDPOINT_ID", None)],
)
def test_model_garden_generate(
    endpoint_os_variable_name: str, result_arg: Optional[str]
) -> None:
    """In order to run this test, you should provide endpoint names.

    Example:
    export FALCON_ENDPOINT_ID=...
    export LLAMA_ENDPOINT_ID=...
    export PROJECT=...
    """
    endpoint_id = os.environ[endpoint_os_variable_name]
    project = os.environ["PROJECT"]
    location = "europe-west4"
    llm = VertexAIModelGarden(
        endpoint_id=endpoint_id,
        project=project,
        result_arg=result_arg,
        location=location,
    )
    output = llm.generate(["What is the meaning of life?", "How much is 2+2"])
    assert isinstance(output, LLMResult)
    assert len(output.generations) == 2


@pytest.mark.skip("CI testing not set up")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint_os_variable_name,result_arg",
    [("FALCON_ENDPOINT_ID", "generated_text"), ("LLAMA_ENDPOINT_ID", None)],
)
async def test_model_garden_agenerate(
    endpoint_os_variable_name: str, result_arg: Optional[str]
) -> None:
    endpoint_id = os.environ[endpoint_os_variable_name]
    project = os.environ["PROJECT"]
    location = "europe-west4"
    llm = VertexAIModelGarden(
        endpoint_id=endpoint_id,
        project=project,
        result_arg=result_arg,
        location=location,
    )
    output = await llm.agenerate(["What is the meaning of life?", "How much is 2+2"])
    assert isinstance(output, LLMResult)
    assert len(output.generations) == 2


@pytest.mark.parametrize(
    "model_name",
    model_names_to_test,
)
def test_vertex_call_count_tokens(model_name: str) -> None:
    llm = VertexAI(model_name=model_name)
    output = llm.get_num_tokens("How are you?")
    assert output == 4
