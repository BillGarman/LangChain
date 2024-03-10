import logging
import time
from typing import Dict, Iterator, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.utils import get_from_env

from langchain_community.document_loaders.base import BaseBlobParser
from langchain_community.document_loaders.blob_loaders import Blob
from langchain_community.utils.openai import is_openai_v1

logger = logging.getLogger(__name__)


class OpenAIWhisperParser(BaseBlobParser):
    """Transcribe and parse audio files.

    Audio transcription is with OpenAI Whisper model.

    Args:
        api_key: OpenAI API key
        chunk_duration_threshold: minimum duration of a chunk in seconds
            NOTE: According to the OpenAI API, the chunk duration should be at least 0.1
            seconds. If the chunk duration is less or equal than the threshold,
            it will be skipped.
    """

    def __init__(
        self, api_key: Optional[str] = None, *, chunk_duration_threshold: float = 0.1
    ):
        self.api_key = api_key
        self.chunk_duration_threshold = chunk_duration_threshold

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """Lazily parse the blob."""

        import io

        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package not found, please install it with "
                "`pip install openai`"
            )
        try:
            from pydub import AudioSegment
        except ImportError:
            raise ImportError(
                "pydub package not found, please install it with " "`pip install pydub`"
            )

        if is_openai_v1():
            # api_key optional, defaults to `os.environ['OPENAI_API_KEY']`
            client = openai.OpenAI(api_key=self.api_key)
        else:
            # Set the API key if provided
            if self.api_key:
                openai.api_key = self.api_key

        # Audio file from disk
        audio = AudioSegment.from_file(blob.path)

        # Define the duration of each chunk in minutes
        # Need to meet 25MB size limit for Whisper API
        chunk_duration = 20
        chunk_duration_ms = chunk_duration * 60 * 1000

        # Split the audio into chunk_duration_ms chunks
        for split_number, i in enumerate(range(0, len(audio), chunk_duration_ms)):
            # Audio chunk
            chunk = audio[i : i + chunk_duration_ms]
            # Skip chunks that are too short to transcribe
            if chunk.duration_seconds <= self.chunk_duration_threshold:
                continue
            file_obj = io.BytesIO(chunk.export(format="mp3").read())
            if blob.source is not None:
                file_obj.name = blob.source + f"_part_{split_number}.mp3"
            else:
                file_obj.name = f"part_{split_number}.mp3"

            # Transcribe
            print(f"Transcribing part {split_number + 1}!")  # noqa: T201
            attempts = 0
            while attempts < 3:
                try:
                    if is_openai_v1():
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1", file=file_obj
                        )
                    else:
                        transcript = openai.Audio.transcribe("whisper-1", file_obj)
                    break
                except Exception as e:
                    attempts += 1
                    print(f"Attempt {attempts} failed. Exception: {str(e)}")  # noqa: T201
                    time.sleep(5)
            else:
                print("Failed to transcribe after 3 attempts.")  # noqa: T201
                continue

            yield Document(
                page_content=transcript.text,
                metadata={"source": blob.source, "chunk": split_number},
            )


class OpenAIWhisperParserLocal(BaseBlobParser):
    """Transcribe and parse audio files with OpenAI Whisper model.

    Audio transcription with OpenAI Whisper model locally from transformers.

    Parameters:
    device - device to use
        NOTE: By default uses the gpu if available,
        if you want to use cpu, please set device = "cpu"
    lang_model - whisper model to use, for example "openai/whisper-medium"
    forced_decoder_ids - id states for decoder in multilanguage model,
        usage example:
        from transformers import WhisperProcessor
        processor = WhisperProcessor.from_pretrained("openai/whisper-medium")
        forced_decoder_ids = WhisperProcessor.get_decoder_prompt_ids(language="french",
          task="transcribe")
        forced_decoder_ids = WhisperProcessor.get_decoder_prompt_ids(language="french",
        task="translate")



    """

    def __init__(
        self,
        device: str = "0",
        lang_model: Optional[str] = None,
        batch_size: int = 8,
        chunk_length: int = 30,
        forced_decoder_ids: Optional[Tuple[Dict]] = None,
    ):
        """Initialize the parser.

        Args:
            device: device to use.
            lang_model: whisper model to use, for example "openai/whisper-medium".
              Defaults to None.
            forced_decoder_ids: id states for decoder in a multilanguage model.
              Defaults to None.
            batch_size: batch size used for decoding
              Defaults to 8.
            chunk_length: chunk length used during inference.
              Defaults to 30s.
        """
        try:
            from transformers import pipeline
        except ImportError:
            raise ImportError(
                "transformers package not found, please install it with "
                "`pip install transformers`"
            )
        try:
            import torch
        except ImportError:
            raise ImportError(
                "torch package not found, please install it with " "`pip install torch`"
            )

        # Determine the device to use
        if device == "cpu":
            self.device = "cpu"
        else:
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        if self.device == "cpu":
            default_model = "openai/whisper-base"
            self.lang_model = lang_model if lang_model else default_model
        else:
            # Set the language model based on the device and available memory
            mem = torch.cuda.get_device_properties(self.device).total_memory / (1024**2)
            if mem < 5000:
                rec_model = "openai/whisper-base"
            elif mem < 7000:
                rec_model = "openai/whisper-small"
            elif mem < 12000:
                rec_model = "openai/whisper-medium"
            else:
                rec_model = "openai/whisper-large"
            self.lang_model = lang_model if lang_model else rec_model

        print("Using the following model: ", self.lang_model)  # noqa: T201

        self.batch_size = batch_size

        # load model for inference
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.lang_model,
            chunk_length_s=chunk_length,
            device=self.device,
        )
        if forced_decoder_ids is not None:
            try:
                self.pipe.model.config.forced_decoder_ids = forced_decoder_ids
            except Exception as exception_text:
                logger.info(
                    "Unable to set forced_decoder_ids parameter for whisper model"
                    f"Text of exception: {exception_text}"
                    "Therefore whisper model will use default mode for decoder"
                )

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """Lazily parse the blob."""

        import io

        try:
            from pydub import AudioSegment
        except ImportError:
            raise ImportError(
                "pydub package not found, please install it with `pip install pydub`"
            )

        try:
            import librosa
        except ImportError:
            raise ImportError(
                "librosa package not found, please install it with "
                "`pip install librosa`"
            )

        # Audio file from disk
        audio = AudioSegment.from_file(blob.path)

        file_obj = io.BytesIO(audio.export(format="mp3").read())

        # Transcribe
        print(f"Transcribing part {blob.path}!")  # noqa: T201

        y, sr = librosa.load(file_obj, sr=16000)

        prediction = self.pipe(y.copy(), batch_size=self.batch_size)["text"]

        yield Document(
            page_content=prediction,
            metadata={"source": blob.source},
        )


class YandexSTTParser(BaseBlobParser):
    """Transcribe and parse audio files.
    Audio transcription is with OpenAI Whisper model."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        iam_token: Optional[str] = None,
        model: str = "general",
        language: str = "auto",
    ):
        """Initialize the parser.

        Args:
            api_key: API key for a service account
            with the `ai.speechkit-stt.user` role.
            iam_token: IAM token for a service account
            with the `ai.speechkit-stt.user` role.
            model: Recognition model name.
              Defaults to general.
            language: The language in ISO 639-1 format.
              Defaults to automatic language recognition.
        Either `api_key` or `iam_token` must be provided, but not both.
        """
        if (api_key is None) == (iam_token is None):
            raise ValueError(
                "Either 'api_key' or 'iam_token' must be provided, but not both."
            )
        self.api_key = api_key
        self.iam_token = iam_token
        self.model = model
        self.language = language

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """Lazily parse the blob."""

        try:
            from speechkit import configure_credentials, creds, model_repository
            from speechkit.stt import AudioProcessingType
        except ImportError:
            raise ImportError(
                "yandex-speechkit package not found, please install it with "
                "`pip install yandex-speechkit`"
            )
        try:
            from pydub import AudioSegment
        except ImportError:
            raise ImportError(
                "pydub package not found, please install it with " "`pip install pydub`"
            )

        if self.api_key:
            configure_credentials(
                yandex_credentials=creds.YandexCredentials(api_key=self.api_key)
            )
        else:
            configure_credentials(
                yandex_credentials=creds.YandexCredentials(iam_token=self.iam_token)
            )

        audio = AudioSegment.from_file(blob.path)

        model = model_repository.recognition_model()

        model.model = self.model
        model.language = self.language
        model.audio_processing_type = AudioProcessingType.Full

        result = model.transcribe(audio)

        for res in result:
            yield Document(
                page_content=res.normalized_text,
                metadata={"source": blob.source},
            )


class AzureAISpeechParser(BaseBlobParser):
    """
    This AzureSpeechServiceParser class make use of the Microsoft Azure Cognitive Speech
    service's transcription module to convert an audio file to text.

    You can find official transcribe sdk documents with this link:

    https://learn.microsoft.com/en-us/python/api/azure-cognitiveservices-speech/azure.cognitiveservices.speech.transcription?view=azure-python

    You can find official transcribe sdk samples with this link:
    https://github.com/Azure-Samples/cognitive-services-speech-sdk/blob/2e39515446ec261bf9fd8d42902147c51c5f72cd/samples/python/console/transcription_sample.py
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        endpoint: Optional[str] = None,
        log_path: Optional[str] = None,
        polling_interval_seconds: float = 0.5,
        speech_recognition_language: Optional[str] = None,
        auto_detect_languages: Optional[list[str]] = None,
        speech_config_kwargs: Optional[dict] = None,
    ) -> None:
        """Initialize the parser.

        See ``speechsdk.SpeechConfig(()`` for more information about how these
        parameters are used.

        Args:
            api_key: The Azure Cognitive Speech service authentication token
            region: The Azure Cognitive Speech service locate region,
                you need this argument or the endpoint argument
            endpoint: The Azure Cognitive Speech service endpoint with wss protocol,
                this would be useful when a programmer uses the Azure cloud other
                than the Azure Global Cloud like Azure China, Azure German
            log_path: pass when transaction job log is required
            polling_interval_seconds: check transcribe job status at this frequency
            auto_detect_languages: pass a list of potential source languages,
                for source language auto-detection in recognition.
            speech_recognition_language: pass a transcribe job's target source languages
        """

        self.api_key = (
            api_key
            if api_key is not None
            else get_from_env("api_key", "AZURE_SPEECH_SERVICE_KEY")
        )

        self.region = (
            region
            if region is not None
            else get_from_env("region", "AZURE_SPEECH_REGION", "NONE")
        )
        self.region = self.region if self.region != "NONE" else None

        self.endpoint = (
            endpoint
            if endpoint is not None
            else get_from_env("endpoint", "AZURE_SPEECH_ENDPOINT", "NONE")
        )
        self.endpoint = self.endpoint if self.endpoint != "NONE" else None

        if not self.region and not self.endpoint:
            raise ValueError(
                "You need to provide either the region or the endpoint argument."
            )

        self.log_path = (
            log_path
            if log_path is not None
            else get_from_env("log_path", "AZURE_SPEECH_LOG_PATH", "NONE")
        )
        self.log_path = self.log_path if self.log_path != "NONE" else None

        self.polling_interval_seconds = polling_interval_seconds

        self.speech_recognition_language = speech_recognition_language
        self.auto_detect_languages = auto_detect_languages
        self.speech_config_kwargs = (
            speech_config_kwargs if speech_config_kwargs is not None else {}
        )

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """Lazily parse the blob."""
        import json

        raw_json_list: List[dict] = []
        document_list: List[Document] = []

        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            raise ImportError(
                "azure.cognitiveservices.speech package not found, please install "
                "it with `pip install azure-cognitiveservices-speech`."
            )

        def conversation_transcriber_recognition_canceled_cb(
            evt: speechsdk.SessionEventArgs,
        ) -> None:
            # Canceled event
            pass

        def conversation_transcriber_session_stopped_cb(
            evt: speechsdk.SessionEventArgs,
        ) -> None:
            # SessionStopped event
            pass

        def conversation_transcriber_transcribed_cb(
            evt: speechsdk.SpeechRecognitionEventArgs,
        ) -> None:
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                evt_dict = json.loads(evt.result.json)

                content = evt_dict["DisplayText"]

                if self.speech_recognition_language is not None:
                    language = self.speech_recognition_language
                elif self.auto_detect_languages is not None:
                    temp_dict = evt_dict["PrimaryLanguage"]
                    language = (
                        temp_dict["Language"] if "Language" in temp_dict else "Unknown"
                    )
                else:
                    language = "Unsigned"

                speaker_id = (
                    evt_dict["SpeakerId"] if "SpeakerId" in evt_dict else "Unknown"
                )
                offset_second = evt_dict["Offset"]
                duration_second = evt_dict["Duration"]

                evt_dict = json.loads(evt.result.json)
                _doc = Document(
                    page_content=content,
                    metadata={
                        "offset_second": int(offset_second) / 10**7,
                        "duration_second": int(duration_second) / 10**7,
                        "language": language,
                        "speaker_id": speaker_id,
                    },
                )
                print(f"TRANSCRIBED:{evt_dict}")
                raw_json_list.append(evt_dict)
                document_list.append(_doc)
            elif evt.result.reason == speechsdk.ResultReason.NoMatch:
                print(
                    "\tNOMATCH: Speech could not be TRANSCRIBED: {}".format(
                        evt.result.no_match_details
                    )
                )

        def conversation_transcriber_session_started_cb(
            evt: speechsdk.SessionEventArgs,
        ) -> None:
            # SessionStarted event
            pass

        def recognize_from_file() -> Iterator[Document]:
            # Speech service speech config
            speech_config = speechsdk.SpeechConfig(
                subscription=self.api_key,
                region=self.region,
                endpoint=self.endpoint,
                speech_recognition_language=self.speech_recognition_language,
                **self.speech_config_kwargs,
            )
            speech_config.output_format = speechsdk.OutputFormat.Detailed

            if self.log_path is not None:
                speech_config.set_property(
                    speechsdk.PropertyId.Speech_LogFilename, self.log_path
                )

            # Speech service audio config
            audio_config = speechsdk.audio.AudioConfig(filename=blob.path)

            # Speech service auto_detect_source_language_config config
            if self.auto_detect_languages is not None:
                auto_detect_source_language_config = (
                    speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                        languages=self.auto_detect_languages
                    )
                )
            else:
                auto_detect_source_language_config = None

            conversation_transcriber = speechsdk.transcription.ConversationTranscriber(
                speech_config=speech_config,
                audio_config=audio_config,
                auto_detect_source_language_config=auto_detect_source_language_config,
            )

            transcribing_stop = False

            def stop_cb(evt: speechsdk.SessionEventArgs) -> None:
                # callback that signals to stop continuous recognition
                # upon receiving an event `evt`
                print("CLOSING on {}".format(evt))
                nonlocal transcribing_stop
                transcribing_stop = True

            # Connect callbacks to the events fired by the conversation transcriber
            conversation_transcriber.transcribed.connect(
                conversation_transcriber_transcribed_cb
            )
            conversation_transcriber.session_started.connect(
                conversation_transcriber_session_started_cb
            )
            conversation_transcriber.session_stopped.connect(
                conversation_transcriber_session_stopped_cb
            )
            conversation_transcriber.canceled.connect(
                conversation_transcriber_recognition_canceled_cb
            )
            # stop transcribing on either session stopped or canceled events
            conversation_transcriber.session_stopped.connect(stop_cb)
            conversation_transcriber.canceled.connect(stop_cb)

            conversation_transcriber.start_transcribing_async()

            # Waits for completion.
            while not transcribing_stop:
                time.sleep(self.polling_interval_seconds)

            conversation_transcriber.stop_transcribing_async()
            return iter(document_list)

        try:
            return recognize_from_file()
        except Exception as err:
            print("Encountered exception. {}".format(err))
            raise err
