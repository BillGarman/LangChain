"""Chain for question-answering against a vector database."""
from typing import Dict, List

from pydantic import BaseModel, Extra

from langchain.chains.base import Chain
from langchain.chains.llm import LLMChain
from langchain.chains.vector_db_qa.prompt import prompt
from langchain.faiss import FAISS
from langchain.llms.base import LLM


class VectorDBQA(Chain, BaseModel):
    """Chain for question-answering against a vector database.

    Example:
        .. code-block:: python

            from langchain import OpenAI, VectorDBQA
            from langchain.faiss import FAISS
            vectordb = FAISS(...)
            vectordbQA = VectorDBQA(llm=OpenAI(), vector_db=vectordb)

    """

    llm: LLM
    """LLM wrapper to use."""
    vector_db: FAISS
    """Vector Database to connect to."""
    input_key: str = "query"  #: :meta private:
    output_key: str = "result"  #: :meta private:

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def input_keys(self) -> List[str]:
        """Return the singular input key.

        :meta private:
        """
        return [self.input_key]

    @property
    def output_keys(self) -> List[str]:
        """Return the singular output key.

        :meta private:
        """
        return [self.output_key]

    def _run(self, inputs: Dict[str, str]) -> Dict[str, str]:
        question = inputs[self.input_key]
        llm_chain = LLMChain(llm=self.llm, prompt=prompt)
        docs = self.vector_db.similarity_search(question)
        contexts = []
        for j, doc in enumerate(docs):
            contexts.append(f"Context {j}:\n{doc.page_content}")
        answer = llm_chain.predict(question=question, context="\n\n".join(contexts))
        return {self.output_key: answer}

    def run(self, question: str) -> str:
        """Run Question-Answering on a vector database.

        Args:
            question: Question to get the answer for.

        Returns:
            The final answer

        Example:
            .. code-block:: python

                answer = vectordbqa.run("What is the capital of Idaho?")
        """
        return self({self.input_key: question})[self.output_key]
