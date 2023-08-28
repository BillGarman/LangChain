"""Chain for applying removals of logical fallacies as described https://arxiv.org/pdf/2212.07425.pdf to the outputs of any other chain. \
Modeled after Constitutional AI and in same format, but applying logical fallacies as generalized rules to remove in output"""
from typing import Any, Dict, List, Optional

from langchain.callbacks.manager import CallbackManagerForChainRun
from langchain.chains.base import Chain
from langchain.chains.fallacy_removal.models import LogicalFallacy 
from langchain.chains.fallacy_removal.fallacies import FALLACIES
from langchain.chains.fallacy_removal.prompts import FALLACY_CRITIQUE_PROMPT, FALLACY_REVISION_PROMPT
from langchain.chains.llm import LLMChain
from langchain.schema import BasePromptTemplate
from langchain.schema.language_model import BaseLanguageModel


class FallacyChain(Chain):
    """Chain for applying logical fallacy evaluations, modeled after Constitutional AI and in same format, but applying logical fallacies as generalized rules to remove in output

    Example:
        .. code-block:: python

            from langchain.llms import OpenAI
            from langchain.chains import LLMChain, FallacyChain
            from langchain.chains.fallacy_removal.models \
                import LogicalFallacy

            llm = OpenAI()

            qa_prompt = PromptTemplate(
                template="Q: {question} A:",
                input_variables=["question"],
            )
            qa_chain = LLMChain(llm=llm, prompt=qa_prompt)

            fallacy_chain = FallacyChain.from_llm(
                llm=llm,
                chain=qa_chain,
                logical_fallacies=[
                    LogicalFallacy(
                        fallacy_critique_request="Tell if this answer meets criteria.",
                        fallacy_revision_request="Give an answer that meets better criteria.",
                    )
                ],
            )

            fallacy_chain.run(question="How do I know if the earth is round?")
    """

    chain: LLMChain
    logical_fallacies: List[LogicalFallacy]
    fallacy_critique_chain: LLMChain
    fallacy_revision_chain: LLMChain
    return_intermediate_steps: bool = False

    @classmethod
    def get_principles(
        cls, names: Optional[List[str]] = None
    ) -> List[LogicalFallacy]:
        if names is None:
            return list(FALLACIES.values())
        else:
            return [FALLACIES[name] for name in names]

    @classmethod
    def from_llm(
        cls,
        llm: BaseLanguageModel,
        chain: LLMChain,
        fallacy_critique_prompt: BasePromptTemplate = FALLACY_CRITIQUE_PROMPT,
        fallacy_revision_prompt: BasePromptTemplate = FALLACY_REVISION_PROMPT,
        **kwargs: Any,
    ) -> "FallacyChain":
        """Create a chain from an LLM."""
        fallacy_critique_chain = LLMChain(llm=llm, prompt=critique_prompt)
        fallacy_revision_chain = LLMChain(llm=llm, prompt=revision_prompt)
        return cls(
            chain=chain,
            fallacy_critique_chain=fallacy_critique_chain,
            fallacy_revision_chain=fallacy_revision_chain,
            **kwargs,
        )

    @property
    def input_keys(self) -> List[str]:
        """Input keys."""
        return self.chain.input_keys

    @property
    def output_keys(self) -> List[str]:
        """Output keys."""
        if self.return_intermediate_steps:
            return ["output", "fallacy_critiques_and_revisions", "initial_output"]
        return ["output"]

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        response = self.chain.run(
            **inputs,
            callbacks=_run_manager.get_child("original"),
        )
        initial_response = response
        input_prompt = self.chain.prompt.format(**inputs)

        _run_manager.on_text(
            text="Initial response: " + response + "\n\n",
            verbose=self.verbose,
            color="yellow",
        )
        fallacy_critiques_and_revisions = []
        for logical_fallacy in self.logical_fallacies:
            # Fallacy critique below

            fallacy_raw_critique = self.fallacy_critique_chain.run(
                input_prompt=input_prompt,
                output_from_model=response,
                fallacy_critique_request=logical_fallacy.fallacy_critique_request,
                callbacks=_run_manager.get_child("fallacy_critique"),
            )
            fallacy_critique = self._parse_critique(
                output_string=fallacy_raw_critique,
            ).strip()

            # if the fallacy critique contains "No fallacy critique needed", then it's the only output
            if "no fallacy critique needed" in fallacy_critique.lower():
                fallacy_critiques_and_revisions.append((fallacy_critique, ""))
                continue

            fallacy_revision = self.revision_chain.run(
                input_prompt=input_prompt,
                output_from_model=response,
                fallacy_critique_request=logical_fallacy.fallacy_critique_request,
                fallacy_critique=fallacy_critique,
                revision_request=logical_fallacy.fallacy_revision_request,
                callbacks=_run_manager.get_child("fallacy_revision"),
            ).strip()
            response = fallacy_revision
            fallacy_critiques_and_revisions.append((fallacy_critique, fallacy_revision))

            _run_manager.on_text(
                text=f"Applying {logical_fallacy.name}..." + "\n\n",
                verbose=self.verbose,
                color="green",
            )

            _run_manager.on_text(
                text="Logical Fallacy: " + fallacy_critique + "\n\n",
                verbose=self.verbose,
                color="blue",
            )

            _run_manager.on_text(
                text="Updated response: " + fallacy_revision + "\n\n",
                verbose=self.verbose,
                color="yellow",
            )

        final_output: Dict[str, Any] = {"output": response}
        if self.return_intermediate_steps:
            final_output["initial_output"] = initial_response
            final_output["fallacy_critiques_and_revisions"] = fallacy_critiques_and_revisions
        return final_output

    @staticmethod
    def _parse_critique(output_string: str) -> str:
        if "Revision request:" not in output_string:
            return output_string
        output_string = output_string.split("Revision request:")[0]
        if "\n\n" in output_string:
            output_string = output_string.split("\n\n")[0]
        return output_string
