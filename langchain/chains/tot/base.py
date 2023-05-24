"""
This a Tree of Thought (ToT) chain based on the paper "Large Language Model
Guided Tree-of-Thought"

https://arxiv.org/pdf/2305.08291.pdf

The Tree of Thought (ToT) chain uses a tree structure to explore the space of
possible solutions to a problem.

"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from enum import Enum
from functools import partial
from textwrap import indent
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, Field

from langchain.base_language import BaseLanguageModel
from langchain.callbacks.manager import (
    AsyncCallbackManagerForChainRun,
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain
from langchain.chains.tot.prompts import FIRST_STEP_PROMPT, NEXT_STEP_PROMPT
from langchain.prompts.base import BasePromptTemplate


class SolutionType(Enum):
    VALID_INTERMEDIATE = 0
    VALID_FINAL = 1
    INVALID = 2


class Result(BaseModel):
    solution: str
    solution_type: SolutionType
    children: set[Result] = Field(default_factory=set)

    def __hash__(self) -> int:
        return id(self)


class ToTPrompter(BaseModel):
    first_step_prompt: BasePromptTemplate
    next_step_prompt: BasePromptTemplate

    def __call__(
        self, problem_description: str, partial_solution_summary: Optional[str] = None
    ) -> str:
        if partial_solution_summary is None:
            return self.first_step_prompt.format(
                problem_description=problem_description
            )
        return self.next_step_prompt.format(
            problem_description=problem_description,
            partial_solution_summary=partial_solution_summary,
        )


class ToTMemory:
    """
    Memory for the Tree of Thought (ToT) chain.
    """

    def __init__(self, stack: Optional[List[Result]] = None):
        self.stack: list[Result] = stack or []

    def top(self) -> Optional[Result]:
        "Get the top of the stack without popping it."
        return self.stack[-1] if len(self.stack) > 0 else None

    def pop(self, n: int = 1) -> Optional[Result]:
        "Pop the top n elements of the stack and return the last one."
        if len(self.stack) < n:
            return None
        for _ in range(n):
            node = self.stack.pop()
        return node

    def top_parent(self) -> Optional[Result]:
        "Get the parent of the top of the stack without popping it."
        return self.stack[-2] if len(self.stack) > 1 else None

    def store(self, node: Result) -> None:
        "Add a node on the top of the stack."
        if len(self.stack) > 0:
            self.stack[-1].children.add(node)
        self.stack.append(node)


class ToTController:
    """
    Tree of Thought (ToT) controller.

    This is a version of a ToT controller, dubbed in the paper as a "Simple
    Controller".

    It has one parameter `c` which is the number of children to explore at each
    node.
    """

    def __init__(self, c: int = 3):
        """
        Initialize the controller.

        Args:
            c: The number of children to explore at each node.
        """
        self.c = c

    def __call__(self, memory: ToTMemory) -> Optional[str]:
        next_node = memory.top()
        parent_node = memory.top_parent()
        solution_type = (
            SolutionType.VALID_INTERMEDIATE
            if next_node is None
            else next_node.solution_type
        )

        # 1 if the current partial solution is invalid, backtrack to the parent node.
        if solution_type == SolutionType.INVALID:
            memory.pop()
            next_node = memory.top()

        # 2 if the current partial solution is valid but C children were
        # explored and yet failed to find a final solution, backtrack to the
        # parent node.
        elif (
            solution_type == SolutionType.VALID_INTERMEDIATE
            and parent_node is not None
            and len(parent_node.children) >= self.c
        ):
            memory.pop(2)
            next_node = memory.top()
        return next_node.solution if next_node is not None else None


class ToTChecker(ABC):
    """
    Tree of Thought (ToT) checker.

    This is an abstract ToT checker that must be implemented by the user. You
    can implement a simple rule-based checker or a more sophisticated
    neural network based classifier.
    """

    @abstractmethod
    def evaluate(self, problem_description: str, response: str) -> SolutionType:
        """
        Evaluate the response to the problem description and return the solution type.
        """

    def __call__(self, problem_description: str, response: str) -> Result:
        return Result(
            solution=response,
            solution_type=self.evaluate(problem_description, response),
        )


class ToTChain(Chain):
    """
    A Chain implementing the Tree of Thought (ToT).
    """

    llm: BaseLanguageModel
    """
    Language model to use. It must be set to produce different variations for
    the same prompt. For the OpenAI use the temperature parameter < 1."""
    # The paper states that authors used the temperature parmaeter set to 1.
    checker: ToTChecker
    """ToT Checker to use."""
    first_step_prompt: BasePromptTemplate = FIRST_STEP_PROMPT
    """Prompt object to use for the first step."""
    next_step_prompt: BasePromptTemplate = NEXT_STEP_PROMPT
    """Prompt object to use for the next steps."""
    output_key: str = "response"  #: :meta private:
    k: int = 10
    """The maximmum number of conversation rounds"""
    tot_memory: ToTMemory = ToTMemory()
    tot_controller: ToTController = ToTController()

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @property
    def tot_prompter(self) -> ToTPrompter:
        return ToTPrompter(
            first_step_prompt=self.first_step_prompt,
            next_step_prompt=self.next_step_prompt,
        )

    @property
    def input_keys(self) -> List[str]:
        """Will be whatever keys the prompt expects.

        :meta private:
        """
        return self.first_step_prompt.input_variables

    @property
    def output_keys(self) -> List[str]:
        """Will always return text key.

        :meta private:
        """
        return [self.output_key]

    def parse_llm_output(self, llm_output: str) -> str:
        """Parse the output of the language model."""
        if match := re.search(r"\{.*?\}", llm_output, re.DOTALL):
            try:
                return json.loads(match.group())["next_step"]
            except json.JSONDecodeError:
                return ""
        return ""

    @property
    def current_level(self) -> int:
        return len(self.tot_memory.stack)

    def log_request(
        self, prompt: str, run_manager: Optional[CallbackManagerForChainRun] = None
    ) -> None:
        if run_manager is not None:
            prefix = "    " * self.current_level
            run_manager.on_text(
                indent(f"ToT Request >>>\n{prompt}\n\n", prefix),
                verbose=self.verbose,
                color="green",
            )

    def log_response(
        self, response: str, run_manager: Optional[CallbackManagerForChainRun] = None
    ) -> None:
        if run_manager is not None:
            prefix = "    " * self.current_level
            run_manager.on_text(
                indent(f"ToT Response >>>\n{response}\n\n", prefix),
                verbose=self.verbose,
                color="green",
            )

    def log_ctrl_signal(
        self,
        ctrl_signal: Optional[str],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> None:
        if ctrl_signal is None:
            ctrl_signal = "<None>"
        if run_manager is not None:
            prefix = "    " * self.current_level
            run_manager.on_text(
                indent(f"ToT Ctrl Signal >>>\n{ctrl_signal}\n\n", prefix),
                verbose=self.verbose,
                color="red",
            )

    def solve(
        self,
        problem_description: str,
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Optional[str]:
        """Algorithm 2 from the ToT paper."""
        checker = partial(self.checker, problem_description)
        llm = self.llm.predict
        controller = self.tot_controller
        prompter = self.tot_prompter
        memory = self.tot_memory

        prompt = prompter(problem_description)
        for _ in range(self.k):
            self.log_request(prompt, run_manager)
            response = self.parse_llm_output(llm(prompt))
            self.log_response(response, run_manager)
            result = checker(response)
            if result.solution_type == SolutionType.VALID_FINAL:
                return result.solution
            memory.store(result)
            ctrl_signal = controller(memory)
            self.log_ctrl_signal(ctrl_signal, run_manager)
            prompt = prompter(problem_description, ctrl_signal)
        return None

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        if run_manager:
            run_manager.on_text(
                text="Starting the ToT solve procedure.\n",
                verbose=self.verbose,
            )
        solution = self.solve(inputs["problem_description"], run_manager)
        if solution is None:
            return {self.output_key: "No solution found"}
        return {self.output_key: solution}

    async def _acall(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForChainRun] = None,
    ) -> Dict[str, str]:
        raise NotImplementedError("Async not implemented yet")

    @property
    def _chain_type(self) -> str:
        return "tot"
