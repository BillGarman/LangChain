import json
from datetime import date
from typing import Iterable
from urllib.parse import urljoin

import pytest
import responses

from langchain.chains import create_cube_query_chain
from langchain.pydantic_v1 import SecretStr
from langchain.utilities.cube import (
    Cube,
    Filter,
    Granularity,
    Operator,
    Order,
    Query,
    TimeDimension,
)
from tests.unit_tests.llms.fake_llm import FakeLLM

CUBE_API_URL = "http://cube-api:4000"
CUBE_API_TOKEN = "TOKEN"
CUBES = [
    {
        "name": "Users",
        "title": "Users",
        "connectedComponent": 1,
        "measures": [
            {
                "name": "users.count",
                "title": "Users Count",
                "shortTitle": "Count",
                "aliasName": "users.count",
                "type": "number",
                "aggType": "count",
                "drillMembers": ["users.id", "users.city", "users.createdAt"],
            }
        ],
        "dimensions": [
            {
                "name": "users.city",
                "title": "Users City",
                "type": "string",
                "aliasName": "users.city",
                "shortTitle": "City",
                "suggestFilterValues": True,
            }
        ],
        "segments": [],
    },
    {
        "name": "Orders",
        "title": "Orders",
        "connectedComponent": 1,
        "measures": [
            {
                "name": "orders.count",
                "title": "Orders Count",
                "shortTitle": "Count",
                "aliasName": "orders.count",
                "type": "number",
                "aggType": "count",
                "drillMembers": ["orders.id", "orders.type", "orders.createdAt"],
            }
        ],
        "dimensions": [
            {
                "name": "orders.type",
                "title": "Orders Type",
                "type": "string",
                "aliasName": "orders.city",
                "shortTitle": "Type",
                "suggestFilterValues": True,
            }
        ],
        "segments": [],
    },
]

PROMPT = f"""Given an input question, first create a syntactically correct Cube query to run, then look at the results of the query and return the answer. Unless the user specifies in his question a specific number of examples he wishes to obtain, always limit your query to at most 5 results. You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific model, only ask for a the few relevant columns given the question.
Pay attention to use only the column names that you can see in the schema description. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
The current date is {date.today().isoformat()}.

Use the following format:
Question: Question here
CubeQuery: Cube Query to run
CubeResult: Result of the CubeQuery
Answer: Final answer here
The output should be formatted as a JSON instance that conforms to the JSON schema below.

As an example, for the schema {{"properties": {{"foo": {{"title": "Foo", "description": "a list of strings", "type": "array", "items": {{"type": "string"}}}}}}, "required": ["foo"]}}
the object {{"foo": ["bar", "baz"]}} is a well-formatted instance of the schema. The object {{"properties": {{"foo": ["bar", "baz"]}}}} is not well-formatted.

Here is the output schema:
```
{{"properties": {{"measures": {{"title": "measure columns", "type": "array", "items": {{"type": "string"}}}}, "dimensions": {{"title": "dimension columns", "type": "array", "items": {{"type": "string"}}}}, "filters": {{"title": "Filters", "type": "array", "items": {{"$ref": "#/definitions/Filter"}}}}, "timeDimensions": {{"title": "Timedimensions", "type": "array", "items": {{"$ref": "#/definitions/TimeDimension"}}}}, "limit": {{"title": "Limit", "type": "integer"}}, "offset": {{"title": "Offset", "type": "integer"}}, "order": {{"description": "The keys are measures columns or dimensions columns to order by.", "type": "object", "additionalProperties": {{"$ref": "#/definitions/Order"}}}}}}, "definitions": {{"Operator": {{"title": "Operator", "description": "An enumeration.", "enum": ["equals", "notEquals", "contains", "notContains", "startsWith", "endsWith", "gt", "gte", "lt", "lte", "set", "notSet", "inDateRange", "notInDateRange", "beforeDate", "afterDate", "measureFilter"]}}, "Filter": {{"title": "Filter", "type": "object", "properties": {{"member": {{"title": "dimension or measure column", "type": "string"}}, "operator": {{"$ref": "#/definitions/Operator"}}, "values": {{"title": "Values", "type": "array", "items": {{"type": "string"}}}}}}, "required": ["member", "operator", "values"]}}, "Granularity": {{"title": "Granularity", "description": "An enumeration.", "enum": ["second", "minute", "hour", "day", "week", "month", "quarter", "year"]}}, "TimeDimension": {{"title": "TimeDimension", "type": "object", "properties": {{"dimension": {{"title": "dimension column", "type": "string"}}, "dateRange": {{"title": "Daterange", "description": "An array of dates with the following format YYYY-MM-DD or in YYYY-MM-DDTHH:mm:ss.SSS format.", "minItems": 2, "maxItems": 2, "type": "array", "items": {{"anyOf": [{{"type": "string", "format": "date-time"}}, {{"type": "string", "format": "date"}}]}}}}, "granularity": {{"description": "A granularity for a time dimension. If you pass null to the granularity, Cube will only perform filtering by a specified time dimension, without grouping.", "allOf": [{{"$ref": "#/definitions/Granularity"}}]}}}}, "required": ["dimension", "dateRange"]}}, "Order": {{"title": "Order", "description": "An enumeration.", "enum": ["asc", "desc"]}}}}}}
```Only use the following meta-information for Cubes defined in the data model:
## Model: Orders

### Measures:
| Title | Description | Column | Type |
| --- | --- | --- | --- |
| Count |  | orders.count | number |

### Dimensions:
| Title | Description | Column | Type |
| --- | --- | --- | --- |
| Type |  | orders.type | string |


## Model: Users

### Measures:
| Title | Description | Column | Type |
| --- | --- | --- | --- |
| Count |  | users.count | number |

### Dimensions:
| Title | Description | Column | Type |
| --- | --- | --- | --- |
| City |  | users.city | string |

Question: How many users are there in New York?
CubeQuery: """  # noqa: E501

QUERY = Query(
    measures=["stories.count"],
    dimensions=["stories.category"],
    filters=[Filter(member="stories.isDraft", operator=Operator.equals, values=["No"])],
    timeDimensions=[
        TimeDimension(
            dimension="stories.time",
            dateRange=[date(2015, 1, 1), date(2015, 12, 31)],
            granularity=Granularity.month,
        )
    ],
    limit=100,
    offset=50,
    order={"stories.time": Order.asc, "stories.count": Order.desc},
)

QUERIES = {
    PROMPT: QUERY.json(),
}


@pytest.fixture(autouse=True)
def mocked_responses() -> Iterable[responses.RequestsMock]:
    """Fixture mocking requests.get."""
    with responses.RequestsMock() as rsps:
        yield rsps


def mocked_mata(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.add(
        method=responses.GET,
        url=urljoin(CUBE_API_URL, "/meta"),
        body=json.dumps({"cubes": CUBES}),
    )


def test_create_cube_query_chain(mocked_responses: responses.RequestsMock) -> None:
    mocked_mata(mocked_responses)

    llm = FakeLLM(queries=QUERIES)

    cube = Cube(
        cube_api_url=CUBE_API_URL,
        cube_api_token=SecretStr(CUBE_API_TOKEN),
    )

    chain = create_cube_query_chain(llm, cube)

    result = chain.invoke({"question": "How many users are there in New York?"})

    assert result == QUERY
