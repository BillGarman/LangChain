try:
    import wandb
except ImportError:
    raise ImportError(
        "You are trying to use wandb which is not currently installed Please install it using pip install wandb"
    )

import hashlib
import json
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd
import spacy
import textstat

from langchain import LLMChain, OpenAI
from langchain.agents import initialize_agent, load_tools
from langchain.callbacks import BaseCallbackHandler, StdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler, CallbackManager
from langchain.chains import LLMChain, SimpleSequentialChain
from langchain.input import print_text
from langchain.prompts import PromptTemplate
from langchain.schema import AgentAction, AgentFinish, LLMResult


def _flatten_dict(nested_dict: Dict[str, Any], parent_key: str = "", sep: str = "_"):
    """
    Generator that yields flattened items from a nested dictionary for a flat dictionary.

    Parameters:
        nested_dict (dict): The nested dictionary to flatten.
        parent_key (str): The prefix to prepend to the keys of the flattened dictionary.
        sep (str): The separator to use between the parent key and the key of the flattened dictionary.

    Yields:
        (str, any): A key-value pair from the flattened dictionary.
    """
    for key, value in nested_dict.items():
        new_key = parent_key + sep + key if parent_key else key
        if isinstance(value, dict):
            yield from _flatten_dict(value, new_key, sep)
        else:
            yield new_key, value


def flatten_dict(nested_dict: Dict[str, Any], parent_key: str = "", sep: str = "_"):
    """Flattens a nested dictionary into a flat dictionary.

    Parameters:
        nested_dict (dict): The nested dictionary to flatten.
        parent_key (str): The prefix to prepend to the keys of the flattened dictionary.
        sep (str): The separator to use between the parent key and the key of the flattened dictionary.

    Returns:
        (dict): A flat dictionary.

    """
    flat_dict = {k: v for k, v in _flatten_dict(nested_dict, parent_key, sep)}
    return flat_dict


def hash_string(s: str):
    """Hash a string using sha1.

    Parameters:
        s (str): The string to hash.

    Returns:
        (str): The hashed string.
    """
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def load_json_to_dict(json_path: Union[str, Path]):
    """Load json file to a dictionary.

    Parameters:
        json_path (str): The path to the json file.

    Returns:
        (dict): The dictionary representation of the json file.
    """
    with open(json_path, "r") as f:
        data = json.load(f)
    return data


def analyze_text(
    text: str,
    complexity_metrics: bool = True,
    visualize: bool = True,
    nlp=None,
    output_dir: Union[str, Path] = None,
):
    """Analyze text using textstat and spacy.

    Parameters:
        text (str): The text to analyze.
        complexity_metrics (bool): Whether to compute complexity metrics.
        visualize (bool): Whether to visualize the text.
        nlp (spacy.lang): The spacy language model to use for visualization.
        output_dir (str): The directory to save the visualization files to.

    Returns:
        (dict): A dictionary containing the complexity metrics and visualization files serialized in a wandb.Html element.
    """
    resp = {}
    if complexity_metrics:
        text_complexity_metrics = {
            "flesch_reading_ease": textstat.flesch_reading_ease(text),
            "flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
            "smog_index": textstat.smog_index(text),
            "coleman_liau_index": textstat.coleman_liau_index(text),
            "automated_readability_index": textstat.automated_readability_index(text),
            "dale_chall_readability_score": textstat.dale_chall_readability_score(text),
            "difficult_words": textstat.difficult_words(text),
            "linsear_write_formula": textstat.linsear_write_formula(text),
            "gunning_fog": textstat.gunning_fog(text),
            "text_standard": textstat.text_standard(text),
            "fernandez_huerta": textstat.fernandez_huerta(text),
            "szigriszt_pazos": textstat.szigriszt_pazos(text),
            "gutierrez_polini": textstat.gutierrez_polini(text),
            "crawford": textstat.crawford(text),
            "gulpease_index": textstat.gulpease_index(text),
            "osman": textstat.osman(text),
        }
        resp.update(text_complexity_metrics)

    if visualize and nlp:
        doc = nlp(text)

        dep_out = spacy.displacy.render(doc, style="dep", jupyter=False, page=True)
        dep_output_path = Path(output_dir, hash_string(f"dep-{text}") + ".html")
        dep_output_path.open("w", encoding="utf-8").write(dep_out)

        ent_out = spacy.displacy.render(doc, style="ent", jupyter=False, page=True)
        ent_output_path = Path(output_dir, hash_string(f"ent-{text}") + ".html")
        ent_output_path.open("w", encoding="utf-8").write(ent_out)

        text_visualizations = {
            "dependency_tree": wandb.Html(str(dep_output_path)),
            "entities": wandb.Html(str(ent_output_path)),
        }
        resp.update(text_visualizations)

    return resp


def construct_html_from_prompt_and_generation(prompt, generation):
    """Construct an html element from a prompt and a generation.

    Parameters:
        prompt (str): The prompt.
        generation (str): The generation.

    Returns:
        (wandb.Html): The html element."""

    formatted_prompt = prompt.replace("\n", "<br>")
    formatted_generation = generation.replace("\n", "<br>")

    return wandb.Html(
        f"""
    <p style="color:black;">{formatted_prompt}:</p>
    <blockquote>
      <p style="color:green;">
        {formatted_generation}
      </p>
    </blockquote>
    """,
        inject=False,
    )


class BaseMetadataCallbackHandler:
    """This class handles the metadata and associated function states for callbacks.

    Attributes:
        step (int): The current step.
        starts (int): The number of times the start method has been called.
        ends (int): The number of times the end method has been called.
        errors (int): The number of times the error method has been called.
        text_ctr (int): The number of times the text method has been called.
        ignore_llm_ (bool): Whether to ignore llm callbacks.
        ignore_chain_ (bool): Whether to ignore chain callbacks.
        ignore_agent_ (bool): Whether to ignore agent callbacks.
        always_verbose_ (bool): Whether to always be verbose.
        chain_starts (int): The number of times the chain start method has been called.
        chain_ends (int): The number of times the chain end method has been called.
        llm_starts (int): The number of times the llm start method has been called.
        llm_ends (int): The number of times the llm end method has been called.
        llm_streams (int): The number of times the text method has been called.
        tool_starts (int): The number of times the tool start method has been called.
        tool_ends (int): The number of times the tool end method has been called.
        agent_ends (int): The number of times the agent end method has been called.
        on_llm_start_records (list): A list of records of the on_llm_start method.
        on_llm_token_records (list): A list of records of the on_llm_token method.
        on_llm_end_records (list): A list of records of the on_llm_end method.
        on_chain_start_records (list): A list of records of the on_chain_start method.
        on_chain_end_records (list): A list of records of the on_chain_end method.
        on_tool_start_records (list): A list of records of the on_tool_start method.
        on_tool_end_records (list): A list of records of the on_tool_end method.
        on_agent_end_records (list): A list of records of the on_agent_end method.
    """

    def __init__(self):
        self.step: int = 0

        self.starts: int = 0
        self.ends: int = 0
        self.errors: int = 0
        self.text_ctr: int = 0

        self.ignore_llm_: bool = False
        self.ignore_chain_: bool = False
        self.ignore_agent_: bool = False
        self.always_verbose_: bool = False

        self.chain_starts: int = 0
        self.chain_ends: int = 0

        self.llm_starts: int = 0
        self.llm_ends: int = 0
        self.llm_streams: int = 0

        self.tool_starts: int = 0
        self.tool_ends: int = 0

        self.agent_ends: int = 0

        self.on_llm_start_records = []
        self.on_llm_token_records = []
        self.on_llm_end_records = []

        self.on_chain_start_records = []
        self.on_chain_end_records = []

        self.on_tool_start_records = []
        self.on_tool_end_records = []

        self.on_text_records = []
        self.on_agent_finish_records = []
        self.on_agent_action_records = []

    @property
    def always_verbose(self) -> bool:
        """Whether to call verbose callbacks even if verbose is False."""
        return self.always_verbose_

    @property
    def ignore_llm(self) -> bool:
        """Whether to ignore LLM callbacks."""
        return self.ignore_llm_

    @property
    def ignore_chain(self) -> bool:
        """Whether to ignore chain callbacks."""
        return self.ignore_chain_

    @property
    def ignore_agent(self) -> bool:
        """Whether to ignore agent callbacks."""
        return self.ignore_agent_

    def get_custom_callback_meta(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "starts": self.starts,
            "ends": self.ends,
            "errors": self.errors,
            "text_ctr": self.text_ctr,
            "chain_starts": self.chain_starts,
            "chain_ends": self.chain_ends,
            "llm_starts": self.llm_starts,
            "llm_ends": self.llm_ends,
            "llm_streams": self.llm_streams,
            "tool_starts": self.tool_starts,
            "tool_ends": self.tool_ends,
            "agent_ends": self.agent_ends,
        }


class WandbCallbackHandler(BaseMetadataCallbackHandler, BaseCallbackHandler):
    """Callback Handler that logs to Weights and Biases.

    Parameters:
        job_type (str): The type of job.
        project (str): The project to log to.
        entity (str): The entity to log to.
        tags (list): The tags to log.
        group (str): The group to log to.
        name (str): The name of the run.
        notes (str): The notes to log.
        visualize (bool): Whether to visualize the run.
        complexity_metrics (bool): Whether to log complexity metrics.
        stream_logs (bool): Whether to stream callback actions to W&B

    This handler will utilize the associated callback method called and formats the input of each callback function with metadata regarding the state of LLM run, and adds the response to the list of records for both the {method}_records and action. It then logs the response using the run.log() method to Weights and Biases.
    """

    def __init__(
        self,
        job_type: Optional[str] = None,
        project: Optional[str] = "langchain_callback_demo",
        entity: Optional[str] = None,
        tags: Optional[Sequence] = None,
        group: Optional[str] = None,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        visualize: bool = False,
        complexity_metrics: bool = False,
        stream_logs: bool = False,
    ) -> None:
        """Initialize callback handler."""
        super().__init__()

        self.job_type = job_type
        self.project = project
        self.entity = entity
        self.tags = tags
        self.group = group
        self.name = name
        self.notes = notes
        self.visualize = visualize
        self.complexity_metrics = complexity_metrics
        self.stream_logs = stream_logs

        self.temp_dir = tempfile.TemporaryDirectory()
        self.run = wandb.init(
            job_type=self.job_type,
            project=self.project,
            entity=self.entity,
            tags=self.tags,
            group=self.group,
            name=self.name,
            notes=self.notes,
        )
        wandb.termwarn(
            """The wandb callback is currently in beta and is subject to change based on updates to `langchain`.
Please report any issues to https://github.com/wandb/wandb/issues with the tag `langchain`.""",
            repeat=False,
        )
        self.callback_columns = []
        self.action_records = []
        self.complexity_metrics = complexity_metrics
        self.visualize = visualize
        self.nlp = spacy.load("en_core_web_sm")

    def _init_resp(self):
        return {k: None for k in self.callback_columns}

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Run when LLM starts."""
        self.step += 1
        self.llm_starts += 1
        self.starts += 1

        resp = self._init_resp()
        resp.update({"action": "on_llm_start"})
        resp.update(flatten_dict(serialized))
        resp.update(self.get_custom_callback_meta())

        for prompt in prompts:
            prompt_resp = deepcopy(resp)
            prompt_resp["prompts"] = prompt
            self.on_llm_start_records.append(prompt_resp)
            self.action_records.append(prompt_resp)
            if self.stream_logs:
                self.run.log(prompt_resp)

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run when LLM generates a new token."""
        self.step += 1
        self.llm_streams += 1

        resp = self._init_resp()
        resp.update({"action": "on_llm_new_token", "token": token})
        resp.update(self.get_custom_callback_meta())

        self.on_llm_token_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        self.step += 1
        self.llm_ends += 1
        self.ends += 1

        resp = self._init_resp()
        resp.update({"action": "on_llm_end"})
        resp.update(flatten_dict(response.llm_output))
        resp.update(self.get_custom_callback_meta())

        for generations in response.generations:
            for generation in generations:
                generation_resp = deepcopy(resp)
                generation_resp.update(flatten_dict(generation.to_dict()))
                generation_resp.update(
                    analyze_text(
                        generation.text,
                        complexity_metrics=self.complexity_metrics,
                        visualize=self.visualize,
                        nlp=self.nlp,
                        output_dir=self.temp_dir.name,
                    )
                )
                self.on_llm_end_records.append(generation_resp)
                self.action_records.append(generation_resp)
                if self.stream_logs:
                    self.run.log(generation_resp)

    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when LLM errors."""
        self.step += 1
        self.errors += 1

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Run when chain starts running."""
        self.step += 1
        self.chain_starts += 1
        self.starts += 1

        resp = self._init_resp()
        resp.update({"action": "on_chain_start"})
        resp.update(flatten_dict(serialized))
        resp.update(self.get_custom_callback_meta())

        chain_input = inputs["input"]

        if isinstance(chain_input, str):
            input_resp = deepcopy(resp)
            input_resp["input"] = chain_input
            self.on_chain_start_records.append(input_resp)
            self.action_records.append(input_resp)
            if self.stream_logs:
                self.run.log(input_resp)
        elif isinstance(chain_input, list):
            for inp in chain_input:
                input_resp = deepcopy(resp)
                input_resp.update(inp)
                self.on_chain_start_records.append(input_resp)
                self.action_records.append(input_resp)
                if self.stream_logs:
                    self.run.log(input_resp)
        else:
            raise ValueError("Unexpected data format provided!")

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Run when chain ends running."""
        self.step += 1
        self.chain_ends += 1
        self.ends += 1

        resp = self._init_resp()
        resp.update({"action": "on_chain_end", "outputs": outputs["output"]})
        resp.update(self.get_custom_callback_meta())

        self.on_chain_end_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_chain_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when chain errors."""
        self.step += 1
        self.errors += 1

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Run when tool starts running."""
        self.step += 1
        self.tool_starts += 1
        self.starts += 1

        resp = self._init_resp()
        resp.update({"action": "on_tool_start", "input_str": input_str})
        resp.update(flatten_dict(serialized))
        resp.update(self.get_custom_callback_meta())

        self.on_tool_start_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Run when tool ends running."""
        self.step += 1
        self.tool_ends += 1
        self.ends += 1

        resp = self._init_resp()
        resp.update({"action": "on_tool_end", "output": output})
        resp.update(self.get_custom_callback_meta())

        self.on_tool_end_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Run when tool errors."""
        self.step += 1
        self.errors += 1

    def on_text(self, text: str, **kwargs: Any) -> None:
        """
        Run when agent is ending.
        """
        self.step += 1
        self.text_ctr += 1

        resp = self._init_resp()
        resp.update({"action": "on_text", "text": text})
        resp.update(self.get_custom_callback_meta())

        self.on_text_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Run when agent ends running."""
        self.step += 1
        self.agent_ends += 1
        self.ends += 1

        resp = self._init_resp()
        resp.update(
            {
                "action": "on_agent_finish",
                "output": finish.return_values["output"],
                "log": finish.log,
            }
        )
        resp.update(self.get_custom_callback_meta())

        self.on_agent_finish_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        """Run on agent action."""
        self.step += 1
        self.tool_starts += 1
        self.starts += 1

        resp = self._init_resp()
        resp.update(
            {
                "action": "on_agent_action",
                "tool": action.tool,
                "tool_input": action.tool_input,
                "log": action.log,
            }
        )
        resp.update(self.get_custom_callback_meta())
        self.on_agent_action_records.append(resp)
        self.action_records.append(resp)
        if self.stream_logs:
            self.run.log(resp)

    def _create_session_analysis_df(self):
        """Create a dataframe with all the information from the session."""
        on_llm_start_records_df = pd.DataFrame(self.on_llm_start_records)
        on_llm_end_records_df = pd.DataFrame(self.on_llm_end_records)

        llm_input_prompts_df = (
            on_llm_start_records_df[["step", "prompts", "name"]]
            .dropna(axis=1)
            .rename({"step": "prompt_step"}, axis=1)
        )
        complexity_metrics_columns = []
        visualizations_columns = []

        if self.complexity_metrics:
            complexity_metrics_columns = [
                "flesch_reading_ease",
                "flesch_kincaid_grade",
                "smog_index",
                "coleman_liau_index",
                "automated_readability_index",
                "dale_chall_readability_score",
                "difficult_words",
                "linsear_write_formula",
                "gunning_fog",
                "text_standard",
                "fernandez_huerta",
                "szigriszt_pazos",
                "gutierrez_polini",
                "crawford",
                "gulpease_index",
                "osman",
            ]

        if self.visualize:
            visualizations_columns = ["dependency_tree", "entities"]

        llm_outputs_df = (
            on_llm_end_records_df[
                [
                    "step",
                    "text",
                    "token_usage_total_tokens",
                    "token_usage_prompt_tokens",
                    "token_usage_completion_tokens",
                ]
                + complexity_metrics_columns
                + visualizations_columns
            ]
            .dropna(axis=1)
            .rename({"step": "output_step", "text": "output"}, axis=1)
        )
        session_analysis_df = pd.concat([llm_input_prompts_df, llm_outputs_df], axis=1)
        session_analysis_df["chat_html"] = session_analysis_df[
            ["prompts", "output"]
        ].apply(
            lambda row: construct_html_from_prompt_and_generation(
                row["prompts"], row["output"]
            ),
            axis=1,
        )
        return session_analysis_df

    def flush_tracker(
        self,
        langchain_asset=None,
        reset: bool = True,
        finish: bool = False,
        job_type: Optional[str] = None,
        project: Optional[str] = None,
        entity: Optional[str] = None,
        tags: Optional[Sequence] = None,
        group: Optional[str] = None,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        visualize: Optional[bool] = None,
        complexity_metrics: Optional[bool] = None,
    ):
        """Flush the tracker and reset the session.

        Args:
            langchain_asset: The langchain asset to save.
            reset: Whether to reset the session.
            finish: Whether to finish the run.
            job_type: The job type.
            project: The project.
            entity: The entity.
            tags: The tags.
            group: The group.
            name: The name.
            notes: The notes.
            visualize: Whether to visualize.
            complexity_metrics: Whether to compute complexity metrics.

            Returns:
                None
        """
        action_records_table = wandb.Table(dataframe=pd.DataFrame(self.action_records))
        session_analysis_table = wandb.Table(
            dataframe=self._create_session_analysis_df()
        )
        self.run.log(
            {
                "action_records": action_records_table,
                "session_analysis": session_analysis_table,
            }
        )

        if langchain_asset:
            langchain_asset_path = Path(self.temp_dir.name, "model.json")
            model_artifact = wandb.Artifact(name="model", type="model")
            model_artifact.add(action_records_table, name="action_records")
            model_artifact.add(session_analysis_table, name="session_analysis")
            try:
                langchain_asset.save(langchain_asset_path)
                model_artifact.add_file(langchain_asset_path)
                model_artifact.metadata = load_json_to_dict(langchain_asset_path)
            except ValueError:
                langchain_asset.save_agent(langchain_asset_path)
                model_artifact.add_file(langchain_asset_path)
                model_artifact.metadata = load_json_to_dict(langchain_asset_path)
            except NotImplementedError:
                pass
            self.run.log_artifact(model_artifact)

        if finish or reset:
            self.run.finish()
            self.temp_dir.cleanup()
        if reset:
            self.__init__(
                job_type=job_type if job_type else self.job_type,
                project=project if project else self.project,
                entity=entity if entity else self.entity,
                tags=tags if tags else self.tags,
                group=group if group else self.group,
                name=name if name else self.name,
                notes=notes if notes else self.notes,
                visualize=visualize if visualize else self.visualize,
                complexity_metrics=complexity_metrics
                if complexity_metrics
                else self.complexity_metrics,
            )


def main():
    """Main function.

    This function is used to test the callback handler.
    Scenarios:
    1. OpenAI LLM
    2. Chain with multiple SubChains on multiple generations
    3. Agent with Tools
    """
    session_group = datetime.now().strftime("%m.%d.%Y_%H.%M.%S")
    wandb_callback = WandbCallbackHandler(
        job_type="inference",
        project="langchain_callback_demo",
        group=f"minimal_{session_group}",
        name="llm",
        tags=["test"],
    )
    manager = CallbackManager([StdOutCallbackHandler(), wandb_callback])
    llm = OpenAI(temperature=0, callback_manager=manager, verbose=True)

    # SCENARIO 1 - LLM
    llm_result = llm.generate(["Tell me a joke", "Tell me a poem"] * 3)
    wandb_callback.flush_tracker(llm, name="simple_sequential")

    # SCENARIO 2 - Chain
    template = """You are a playwright. Given the title of play, it is your job to write a synopsis for that title.
    Title: {title}
    Playwright: This is a synopsis for the above play:"""
    prompt_template = PromptTemplate(input_variables=["title"], template=template)
    synopsis_chain = LLMChain(llm=llm, prompt=prompt_template, callback_manager=manager)

    template = """You are a play critic from the New York Times. Given the synopsis of play, it is your job to write a review for that play.
    Play Synopsis:
    {synopsis}
    Review from a New York Times play critic of the above play:"""
    prompt_template = PromptTemplate(input_variables=["synopsis"], template=template)
    review_chain = LLMChain(llm=llm, prompt=prompt_template, callback_manager=manager)

    overall_chain = SimpleSequentialChain(
        chains=[synopsis_chain, review_chain], verbose=True, callback_manager=manager
    )

    test_prompts = [
        {
            "input": "documentary about good video games that push the boundary of game design"
        },
        {"input": "cocaine bear vs heroin wolf"},
        {"input": "the best in class mlops tooling"},
    ]
    overall_chain.apply(test_prompts)
    wandb_callback.flush_tracker(overall_chain, name="agent")

    # SCENARIO 3 - Agent with Tools
    tools = load_tools(["serpapi", "llm-math"], llm=llm, callback_manager=manager)
    agent = initialize_agent(
        tools,
        llm,
        agent="zero-shot-react-description",
        callback_manager=manager,
        verbose=True,
    )
    agent.run(
        "Who is Leo DiCaprio's girlfriend? What is her current age raised to the 0.43 power?"
    )
    wandb_callback.flush_tracker(agent, reset=False, finish=True)


if __name__ == "__main__":
    main()
