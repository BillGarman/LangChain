import tempfile
from enum import Enum
from typing import Any, Dict, Optional, Union

from langchain.callbacks.manager import CallbackManagerForToolRun
from langchain.pydantic_v1 import root_validator
from langchain.tools.audio_utils import load_audio, save_audio
from langchain.tools.base import BaseTool
from langchain.utils import get_from_dict_or_env


def _import_elevenlabs() -> Any:
    try:
        import elevenlabs
    except ImportError as e:
        raise ImportError(
            "Cannot import elevenlabs, please install `pip install elevenlabs`."
        ) from e
    return elevenlabs


class ElevenLabsModel(str, Enum):
    """Models available for Eleven Labs Text2Speech."""

    MULTI_LINGUAL = "eleven_multilingual_v1"
    MONO_LINGUAL = "eleven_monolingual_v1"


class ElevenLabsText2SpeechTool(BaseTool):
    """Tool that queries the Eleven Labs Text2Speech API.

    In order to set this up, follow instructions at:
    https://docs.elevenlabs.io/welcome/introduction
    """

    model: Union[ElevenLabsModel, str] = ElevenLabsModel.MULTI_LINGUAL

    name: str = "eleven_labs_text2speech"
    description: str = (
        "A wrapper around Eleven Labs Text2Speech. "
        "Useful for when you need to convert text to speech. "
        "It supports multiple languages, including English, German, Polish, "
        "Spanish, Italian, French, Portuguese, and Hindi. "
    )

    @root_validator(pre=True)
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key exists in environment."""
        _ = get_from_dict_or_env(values, "eleven_api_key", "ELEVEN_API_KEY")

        return values

    def _run(
        self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        """Use the tool."""
        elevenlabs = _import_elevenlabs()
        try:
            speech = elevenlabs.generate(text=query, model=self.model)
            self.play(speech)
            return "Speech has been generated"
        except Exception as e:
            raise RuntimeError(f"Error while running ElevenLabsText2SpeechTool: {e}")

    def play(self, speech: bytes) -> None:
        """Play the text as speech."""
        elevenlabs = _import_elevenlabs()
        elevenlabs.play(speech)

    def stream_speech(self, query: str) -> None:
        """Stream the text as speech as it is generated.
        Play the text in your speakers."""
        elevenlabs = _import_elevenlabs()
        speech_stream = elevenlabs.generate(text=query, model=self.model, stream=True)
        elevenlabs.stream(speech_stream)

    def generate_and_save(self, query: str) -> str:
        """Save the text as speech to a temporary file."""
        elevenlabs = _import_elevenlabs()
        speech = elevenlabs.generate(text=query, model=self.model)
        path = save_audio(speech)
        return path

    def load_and_play(self, path: str) -> None:
        """Load the text as speech from a temporary file and play it."""
        speech = load_audio(path)
        self.play(speech)
