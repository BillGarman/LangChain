"""Integration test for self ask with search."""

from langchain.docstore.wikipedia import Wikipedia
from langchain.llms.openai import OpenAI
from langchain.agents.react.base import ReActChain


def test_react() -> None:
    """Test functionality on a prompt."""
    llm = OpenAI(temperature=0)
    react = ReActChain(llm=llm, docstore=Wikipedia())
    question = (
        "Author David Chanoff has collaborated with a U.S. Navy admiral "
        "who served as the ambassador to the United Kingdom under "
        "which President?"
    )
    output = react.run(question)
    assert output == "Bill Clinton"
