from langchain import llms
from langchain.llms.base import BaseLLM

EXPECT_ALL = [
    "AI21",
    "AlephAlpha",
    "AmazonAPIGateway",
    "Anthropic",
    "Anyscale",
    "Arcee",
    "Aviary",
    "AzureMLOnlineEndpoint",
    "AzureOpenAI",
    "Banana",
    "Baseten",
    "Beam",
    "Bedrock",
    "CTransformers",
    "CTranslate2",
    "CerebriumAI",
    "ChatGLM",
    "Clarifai",
    "Cohere",
    "Databricks",
    "DeepInfra",
    "DeepSparse",
    "EdenAI",
    "FakeListLLM",
    "Fireworks",
    "ForefrontAI",
    "GigaChat",
    "GPT4All",
    "GooglePalm",
    "GooseAI",
    "GradientLLM",
    "HuggingFaceEndpoint",
    "HuggingFaceHub",
    "HuggingFacePipeline",
    "HuggingFaceTextGenInference",
    "HumanInputLLM",
    "KoboldApiLLM",
    "LlamaCpp",
    "TextGen",
    "ManifestWrapper",
    "Minimax",
    "MlflowAIGateway",
    "Modal",
    "MosaicML",
    "Nebula",
    "NIBittensorLLM",
    "NLPCloud",
    "Ollama",
    "OpenAI",
    "OpenAIChat",
    "OpenLLM",
    "OpenLM",
    "PaiEasEndpoint",
    "Petals",
    "PipelineAI",
    "Predibase",
    "PredictionGuard",
    "PromptLayerOpenAI",
    "PromptLayerOpenAIChat",
    "OpaquePrompts",
    "RWKV",
    "Replicate",
    "SagemakerEndpoint",
    "SelfHostedHuggingFaceLLM",
    "SelfHostedPipeline",
    "StochasticAI",
    "TitanTakeoff",
    "TitanTakeoffPro",
    "Tongyi",
    "VertexAI",
    "VertexAIModelGarden",
    "VLLM",
    "VLLMOpenAI",
    "Writer",
    "OctoAIEndpoint",
    "Xinference",
    "JavelinAIGateway",
    "QianfanLLMEndpoint",
    "YandexGPT",
    "VolcEngineMaasLLM",
    "WatsonxLLM",
    "SparkLLM",
]


def test_all_imports() -> None:
    """Simple test to make sure all things can be imported."""
    for cls in llms.__all__:
        assert issubclass(getattr(llms, cls), BaseLLM)
    assert set(llms.__all__) == set(EXPECT_ALL)
