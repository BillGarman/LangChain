from typing import List, Any, Optional

from langchain.chat_models.base import BaseChatModel
from langchain.schema import ChatResult
from langchain.schema.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
)
from langchain.callbacks.manager import (
    CallbackManagerForLLMRun,
)

B_INST, E_INST = "[INST]", "[/INST]"
B_SYS, E_SYS = "<<SYS>>", "<</SYS>>"


class ChatLlama2(BaseChatModel):
    _pipeline: Any #: :meta private:

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "llama-2-chat-hf"

    @property
    def pipeline(self) -> Any:
        """Getter for the pipeline."""
        return self._pipeline

    @pipeline.setter
    def pipeline(self, value: Any):
        """Setter for the pipeline."""
        if not hasattr(value, "task") or value.task != "text-generation":
            raise ValueError("The pipeline task should be 'text-generation'.")

        valid_models = (
            "meta-llama/Llama-2-7b-chat-hf",
            "meta-llama/Llama-2-13b-chat-hf",
            "meta-llama/Llama-2-70b-chat-hf",
        )

        if not hasattr(value, "model") or value.model.name_or_path not in valid_models:
            raise ValueError(f"The pipeline model name or path should be one of {valid_models}.")

        self._pipeline = value

    def _format_messages_as_text(self, messages: List[BaseMessage]) -> str:
        """ https://huggingface.co/blog/llama2 """
        prompt = ""

        for i, message in enumerate(messages):
            if i != 0 and isinstance(message, SystemMessage):
                raise ...
            elif i == 0 and isinstance(message, SystemMessage):
                prompt += f"<s>{B_INST} {B_SYS}\n{message.content}\n{E_SYS}\n\n"
            elif isinstance(message, HumanMessage) and i > 0:
                prompt += f"{message.content} {E_INST} "
            elif i == 0 and isinstance(message, HumanMessage):
                prompt += f"<s>{B_INST} {message.content} {E_INST} "
            elif isinstance(message, AIMessage):
                prompt += f"{message.content} </s><s>{B_INST} "
        
        return prompt

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = self._format_messages_as_text(messages)
        # TODO: remove
        print(prompt)

        pipeline_params = kwargs
        # ensure that:
        kwargs["return_text"] = True
        kwargs["return_full_text"] = False
        # num_return_sequences ? ~ is it possible to pass multiple conversations ?

        response = self.pipeline(prompt, **pipeline_params)["generated_text"]
        print(response)
        ...
        return response

# TODO:
# fix problem with getter
# correct output from _generate
# try to add stopping criteria
# handle batch requests
# handle ChatMessage, AIMessageChunk ?
