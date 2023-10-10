from typing import Any, List, Mapping, Optional

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.llms.utils import enforce_stop_tokens
from langchain.pydantic_v1 import Extra


DEFAULT_MODEL_ID = "google/flan-t5-large"
DEFAULT_TASK = "text2text-generation"
VALID_TASKS = ("text2text-generation", "text-generation", "summarization")


class WeightOnlyQuantPipeline(LLM):
    """Weight only quantized model.

    To use, you should have the `intel-extension-for-transformers` packabge and `transformers` package installed.
    intel-extension-for-transformers: https://github.com/intel/intel-extension-for-transformers

    Example using from_model_id:
        .. code-block:: python

            from langchain.llms import WeightOnlyQuantPipeline
            from intel_extension_for_transformers.transformers import WeightOnlyQuantConfig
            config = WeightOnlyQuantConfig
            hf = WeightOnlyQuantPipeline.from_model_id(
                model_id="google/flan-t5-large",
                task="text2text-generation"
                pipeline_kwargs={"max_new_tokens": 10},
                quantization_config=config,
            )
    Example passing pipeline in directly:
        .. code-block:: python

            from langchain.llms import WeightOnlyQuantPipeline
            from intel_extension_for_transformers.transformers import AutoModelForSeq2SeqLM
            from intel_extension_for_transformers.transformers import WeightOnlyQuantConfig
            from transformers import AutoTokenizer, pipeline

            model_id = "google/flan-t5-large"
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            config = WeightOnlyQuantConfig
            model = AutoModelForSeq2SeqLM.from_pretrained(model_id, quantization_config=config)
            pipe = pipeline(
                "text-generation", model=model, tokenizer=tokenizer, max_new_tokens=10
            )
            hf = WeightOnlyQuantPipeline(pipeline=pipe)
    """

    pipeline: Any  #: :meta private:
    model_id: str = DEFAULT_MODEL_ID
    """Model name or local path to use."""

    model_kwargs: Optional[dict] = None
    """Key word arguments passed to the model."""

    pipeline_kwargs: Optional[dict] = None
    """Key word arguments passed to the pipeline."""

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.allow

    @classmethod
    def from_model_id(
        cls,
        model_id: str,
        task: str,
        device: int = -1,
        model_kwargs: Optional[dict] = None,
        pipeline_kwargs: Optional[dict] = None,
        load_in_4bit: Optional[bool] = False,
        load_in_8bit: Optional[bool] = False,
        quantization_config=None,
        **kwargs: Any,
    ) -> LLM:
        """Construct the pipeline object from model_id and task."""
        try:
            from intel_extension_for_transformers.transformers import (
                AutoModelForCausalLM,
                AutoModelForSeq2SeqLM,
            )
            from transformers import AutoTokenizer, pipeline as hf_pipeline
        except ImportError:
            raise ValueError(
                "Could not import transformers python package. "
                "Please install it with `pip install transformers` "
                "and `pip install intel-extension-for-transformers`."
            )

        _model_kwargs = model_kwargs or {}
        tokenizer = AutoTokenizer.from_pretrained(model_id, **_model_kwargs)

        try:
            if task == "text-generation":
                model = AutoModelForCausalLM.from_pretrained(model_id,
                                                             load_in_4bit=load_in_4bit,
                                                             load_in_8bit=load_in_8bit,
                                                             quantization_config=quantization_config,
                                                             use_llm_runtime=False,
                                                             **_model_kwargs)
            elif task in ("text2text-generation", "summarization"):
                model = AutoModelForSeq2SeqLM.from_pretrained(model_id,
                                                              load_in_4bit=load_in_4bit,
                                                              load_in_8bit=load_in_8bit,
                                                              quantization_config=quantization_config,
                                                              use_llm_runtime=False,
                                                              **_model_kwargs)
            else:
                raise ValueError(
                    f"Got invalid task {task}, "
                    f"currently only {VALID_TASKS} are supported"
                )
        except ImportError as e:
            raise ValueError(
                f"Could not load the {task} model due to missing dependencies."
            ) from e

        if "trust_remote_code" in _model_kwargs:
            _model_kwargs = {
                k: v for k, v in _model_kwargs.items() if k != "trust_remote_code"
            }
        _pipeline_kwargs = pipeline_kwargs or {}
        pipeline = hf_pipeline(
            task=task,
            model=model,
            tokenizer=tokenizer,
            device=device,
            model_kwargs=_model_kwargs,
            **_pipeline_kwargs,
        )
        if pipeline.task not in VALID_TASKS:
            raise ValueError(
                f"Got invalid task {pipeline.task}, "
                f"currently only {VALID_TASKS} are supported"
            )
        return cls(
            pipeline=pipeline,
            model_id=model_id,
            model_kwargs=_model_kwargs,
            pipeline_kwargs=_pipeline_kwargs,
            **kwargs,
        )

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "model_id": self.model_id,
            "model_kwargs": self.model_kwargs,
            "pipeline_kwargs": self.pipeline_kwargs,
        }

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "weight_only_quantization"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call the HuggingFace model and return the output.

        Args:
            prompt: The prompt to use for generation.
            stop: A list of strings to stop generation when encountered.

        Returns:
            The generated text.

        Example:
            .. code-block:: python

                from langchain.llms import WeightOnlyQuantPipeline
                llm = WeightOnlyQuantPipeline.from_model_id(model_id="google/flan-t5-large",
                                                         task="text2text-generation")
                llm("This is a prompt.")
        """
        response = self.pipeline(prompt)
        if self.pipeline.task == "text-generation":
            # Text generation return includes the starter text.
            text = response[0]["generated_text"][len(prompt) :]
        elif self.pipeline.task == "text2text-generation":
            text = response[0]["generated_text"]
        elif self.pipeline.task == "summarization":
            text = response[0]["summary_text"]
        else:
            raise ValueError(
                f"Got invalid task {self.pipeline.task}, "
                f"currently only {VALID_TASKS} are supported"
            )
        if stop:
            # This is a bit hacky, but I can't figure out a better way to enforce
            # stop tokens when making calls to huggingface_hub.
            text = enforce_stop_tokens(text, stop)
        return text
