import re

import numpy as np
import pytest
from pandas import DataFrame

from langchain.agents import create_pandas_dataframe_agent
from langchain.agents.agent import AgentExecutor
from langchain.llms import OpenAI


@pytest.fixture(scope="function")
def data() -> DataFrame:
    random_data = np.random.rand(4, 4)
    df = DataFrame(random_data, columns=["name", "age", "food", "sport"])
    return df


def test_pandas_agent_creation(df: DataFrame) -> None:
    agent = create_pandas_dataframe_agent(OpenAI(temperature=0), df)
    assert isinstance(agent, AgentExecutor)


def test_data_reading(df: DataFrame) -> None:
    agent = create_pandas_dataframe_agent(OpenAI(temperature=0), df)
    assert isinstance(agent, AgentExecutor)
    response = agent.run("how many rows in df? Give me a number.")
    result = re.search(rf".*({df.shape[0]}).*", response)
    assert result is not None
    assert result.group(1) is not None
