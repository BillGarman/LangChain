import json
from datetime import date
from typing import Iterable
from urllib.parse import urljoin

import pytest
import responses
from pydantic.v1 import SecretStr

from langchain.tools.cube.tool import LoadCubeTool, MetaInformationCubeTool, ListCubeTool
from langchain.utilities.cube import Cube

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
                "drillMembers": ["users.id", "users.city", "users.createdAt"]
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
        "segments": []
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
                "drillMembers": ["orders.id", "orders.type", "orders.createdAt"]
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
        "segments": []
    }
]


@pytest.fixture(autouse=True)
def mocked_responses() -> Iterable[responses.RequestsMock]:
    """Fixture mocking requests.get."""
    with responses.RequestsMock() as rsps:
        yield rsps


def mocked_mata(mocked_responses: responses.RequestsMock):
    mocked_responses.add(
        method=responses.GET,
        url=urljoin(CUBE_API_URL, "/meta"),
        body=json.dumps({
            "cubes": CUBES
        }),
    )


def mocked_load(mocked_responses: responses.RequestsMock):
    mocked_responses.add(
        method=responses.POST,
        url=urljoin(CUBE_API_URL, "/load"),
        body=json.dumps({
            "query": {
                "measures": ["users.count"],
                "filters": [],
                "timezone": "UTC",
                "dimensions": [],
                "timeDimensions": []
            },
            "data": [
                {
                    "users.count": "700"
                }
            ],
            "annotation": {
                "measures": {
                    "users.count": {
                        "title": "Users Count",
                        "shortTitle": "Count",
                        "type": "number"
                    }
                },
                "dimensions": {},
                "segments": {},
                "timeDimensions": {}
            }
        }),
    )


def mocked_sql(mocked_responses: responses.RequestsMock):
    mocked_responses.add(
        method=responses.POST,
        url=urljoin(CUBE_API_URL, "/sql"),
        body=json.dumps({
            "sql": {
                "sql": [
                    "SELECT date_trunc('day', (users.created_at::timestamptz AT TIME ZONE 'UTC')) \"users.created_at_date\", count(users.id) \"users.count\"\n    FROM\n      public.users AS users\n  WHERE (users.created_at >= $1::timestamptz AND users.created_at <= $2::timestamptz) GROUP BY 1 ORDER BY 1 ASC LIMIT 10000",
                    ["2019-03-01T00:00:00Z", "2019-03-31T23:59:59Z"]
                ],
                "timeDimensionAlias": "users.created_at_date",
                "timeDimensionField": "users.createdAt",
                "order": [
                    {
                        "id": "users.createdAt",
                        "desc": False
                    }
                ],
                "cacheKeyQueries": {
                    "queries": [
                        ["select max(users.created_at) from public.users AS users", []]
                    ],
                    "renewalThreshold": 21600
                },
                "preAggregations": []
            }
        })
    )


def test_load_cube_tool(mocked_responses: responses.RequestsMock):
    """Test the load cube tool."""
    mocked_mata(mocked_responses)
    mocked_load(mocked_responses)

    cube = Cube(
        cube_api_url=CUBE_API_URL,
        cube_api_token=SecretStr(CUBE_API_TOKEN),
    )

    tool = LoadCubeTool(cube=cube)

    description = """Input to this tool is a detailed and correct Cube query, it format is JSON. Output is a result from the Cube, it format is JSON.This current date is """ + date.today().isoformat() + """.If the query is not correct, an error message will be returned.If an error is returned, rewrite the query, check the query, and try again.
The input should be formatted as a JSON instance that conforms to the JSON schema below.
As an example, for the schema {{"properties": {{"foo": {{"title": "Foo", "description": "a list of strings", "type": "array", "items": {{"type": "string"}}}}}}, "required": ["foo"]}}
the object {{"foo": ["bar", "baz"]}} is a well-formatted instance of the schema. The object {{"properties": {{"foo": ["bar", "baz"]}}}} is not well-formatted.
Here is the input schema:
```
{{"properties": {{"measures": {{"title": "measure columns", "type": "array", "items": {{"type": "string"}}}}, "dimensions": {{"title": "dimension columns", "type": "array", "items": {{"type": "string"}}}}, "filters": {{"title": "Filters", "type": "array", "items": {{"$ref": "#/definitions/Filter"}}}}, "timeDimensions": {{"title": "Timedimensions", "type": "array", "items": {{"$ref": "#/definitions/TimeDimension"}}}}, "limit": {{"title": "Limit", "type": "integer"}}, "offset": {{"title": "Offset", "type": "integer"}}, "order": {{"description": "The keys are measures columns or dimensions columns to order by.", "type": "object", "additionalProperties": {{"$ref": "#/definitions/Order"}}}}}}, "definitions": {{"Operator": {{"title": "Operator", "description": "An enumeration.", "enum": ["equals", "notEquals", "contains", "notContains", "startsWith", "endsWith", "gt", "gte", "lt", "lte", "set", "notSet", "inDateRange", "notInDateRange", "beforeDate", "afterDate", "measureFilter"]}}, "Filter": {{"title": "Filter", "type": "object", "properties": {{"member": {{"title": "dimension or measure column", "type": "string"}}, "operator": {{"$ref": "#/definitions/Operator"}}, "values": {{"title": "Values", "type": "array", "items": {{"type": "string"}}}}}}, "required": ["member", "operator", "values"]}}, "Granularity": {{"title": "Granularity", "description": "An enumeration.", "enum": ["second", "minute", "hour", "day", "week", "month", "quarter", "year"]}}, "TimeDimension": {{"title": "TimeDimension", "type": "object", "properties": {{"dimension": {{"title": "dimension column", "type": "string"}}, "dateRange": {{"title": "Daterange", "description": "An array of dates with the following format YYYY-MM-DD or in YYYY-MM-DDTHH:mm:ss.SSS format.", "minItems": 2, "maxItems": 2, "type": "array", "items": {{"anyOf": [{{"type": "string", "format": "date-time"}}, {{"type": "string", "format": "date"}}]}}}}, "granularity": {{"description": "A granularity for a time dimension. If you pass null to the granularity, Cube will only perform filtering by a specified time dimension, without grouping.", "allOf": [{{"$ref": "#/definitions/Granularity"}}]}}}}, "required": ["dimension", "dateRange"]}}, "Order": {{"title": "Order", "description": "An enumeration.", "enum": ["asc", "desc"]}}}}}}
```"""

    assert tool.description == description
    assert tool.run('{"measures": ["orders.count"], "dimensions": ["orders.type"]}') == '[{"users.count": "700"}]'


def test_meta_information_cube_tool(mocked_responses: responses.RequestsMock):
    """Test the meta information cube tool."""
    mocked_mata(mocked_responses)

    cube = Cube(
        cube_api_url=CUBE_API_URL,
        cube_api_token=SecretStr(CUBE_API_TOKEN),
    )

    meta_information = """## Model: Users

### Measures:
| Title | Description | Column | Type |
| --- | --- | --- | --- |
| Count |  | users.count | number |

### Dimensions:
| Title | Description | Column | Type |
| --- | --- | --- | --- |
| City |  | users.city | string |
"""

    tool = MetaInformationCubeTool(cube=cube)
    assert tool.run("Users") == meta_information


def test_list_cube_tool(mocked_responses: responses.RequestsMock):
    """Test the list cube tool."""
    mocked_mata(mocked_responses)

    cube = Cube(
        cube_api_url=CUBE_API_URL,
        cube_api_token=SecretStr(CUBE_API_TOKEN),
    )

    tool = ListCubeTool(cube=cube)

    assert tool.run("") == """| Model | Description |
| --- | --- |
| Users | Users |
| Orders | Orders |
"""
