import os
import openai
from typing import List, Iterator
from langchain.docstore.document import Document
from langchain.document_loaders.generic import GenericLoader

class AudioFileLoader(GenericLoader):
    """Document loader for audio files using audio-to-text transcription with OpenAI Whisper model.
    
    Example:

    .. code-block:: python
        from langchain.document_loaders import AudioFileLoader
        audio_file_path = "/path/to/directory"
        loader = AudioFileLoader(audio_file_path)
        loader.load()
    """

    def __init__(self, audio_file_path: str):
        """Initialize with path to audio file. 

        Args:
            audio_file_path: Path to directory to load from
        """
        self.audio_file_path = audio_file_path

    def lazy_load(self) -> Iterator[Document]:
        """Transcribe audio file to text w/ OpenAI Whisper API."""
        audio_file = open(self.audio_file_path , 'rb')
        fpath , fname = os.path.split(self.audio_file_path)
        transcript = openai.Audio.transcribe("whisper-1",audio_file)
        yield Document(page_content=transcript.text,metadata={"source":fname})
    
    def load(self) -> List[Document]:
        return list(self.lazy_load())