"""BasePrompt schema definition."""
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from langchain.formatting import formatter

DEFAULT_FORMATTER_MAPPING = {
    "f-string": formatter.format,
}


def cleanup_prompt_dict(prompt_dict: Dict) -> None:
    """Remove any empty keys from prompt dictionary."""
    keys_to_delete = []
    for key, val in prompt_dict.items():
        if not val:
            keys_to_delete.append(key)
    for key in keys_to_delete:
        del prompt_dict[key]


def check_valid_template(
    template: str, template_format: str, input_variables: List[str]
) -> None:
    """Check that template string is valid."""
    if template_format not in DEFAULT_FORMATTER_MAPPING:
        valid_formats = list(DEFAULT_FORMATTER_MAPPING)
        raise ValueError(
            f"Invalid template format. Got `{template_format}`;"
            f" should be one of {valid_formats}"
        )
    dummy_inputs = {input_variable: "foo" for input_variable in input_variables}
    try:
        formatter_func = DEFAULT_FORMATTER_MAPPING[template_format]
        formatter_func(template, **dummy_inputs)
    except KeyError:
        raise ValueError("Invalid prompt schema.")


class BasePromptTemplate(ABC):
    """Base prompt should expose the format method, returning a prompt."""

    input_variables: List[str]
    """A list of the names of the variables the prompt template expects."""

    @abstractmethod
    def format(self, **kwargs: Any) -> str:
        """Format the prompt with the inputs.

        Args:
            kwargs: Any arguments to be passed to the prompt template.

        Returns:
            A formatted string.

        Example:

        .. code-block:: python

            prompt.format(variable1="foo")
        """

    @abstractmethod
    def _prompt_dict(self) -> Dict:
        """Return a dictionary of the prompt."""

    def save(self, file_path: Union[Path, str]) -> None:
        """Save the prompt.

        Args:
            file_path: Path to directory to save prompt to.
        Returns:
            The name of the saved prompt file.

        Example:

        .. code-block:: python

            prompt.save(save_path="path/")
        """
        # Convert file to Path object.
        if isinstance(file_path, str):
            save_path = Path(file_path)
        else:
            save_path = file_path

        directory_path = Path("/".join(save_path.parts[:-1]))
        directory_path.mkdir(parents=True, exist_ok=True)

        # Fetch dictionary to save
        prompt_dict = self._prompt_dict()

        if save_path.suffix == ".json":
            with open(file_path, "w") as f:
                f.write(json.dumps(prompt_dict, indent=4))
        elif save_path.suffix == ".yaml":
            with open(file_path, "w") as f:
                yaml.dump(prompt_dict, f, default_flow_style=False)
        else:
            raise ValueError(f"{save_path} must be json or yaml")
