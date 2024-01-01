from copy import deepcopy
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple


def _retrieve_ref(path: str, schema: dict) -> dict:
    components = path.split("/")
    if components[0] != "#":
        raise ValueError(
            "ref paths are expected to be URI fragments, meaning they should start "
            "with #."
        )
    out = schema
    for component in components[1:]:
        out = out[component]
    return deepcopy(out)


def _dereference_refs_helper(
    obj: Any, full_schema: dict, skip_keys: Sequence[str]
) -> Any:
    if isinstance(obj, dict):
        obj_out = {}
        for k, v in obj.items():
            if k in skip_keys:
                obj_out[k] = v
            elif k == "$ref":
                ref = _retrieve_ref(v, full_schema)
                return _dereference_refs_helper(ref, full_schema, skip_keys)
            elif isinstance(v, (list, dict)):
                obj_out[k] = _dereference_refs_helper(v, full_schema, skip_keys)
            else:
                obj_out[k] = v
        return obj_out
    elif isinstance(obj, list):
        return [_dereference_refs_helper(el, full_schema, skip_keys) for el in obj]
    else:
        return obj


def _infer_skip_keys(obj: Any, full_schema: dict) -> List[str]:
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "$ref":
                ref = _retrieve_ref(v, full_schema)
                keys.append(v.split("/")[1])
                keys += _infer_skip_keys(ref, full_schema)
            elif isinstance(v, (list, dict)):
                keys += _infer_skip_keys(v, full_schema)
    elif isinstance(obj, list):
        for el in obj:
            keys += _infer_skip_keys(el, full_schema)
    return keys


def dereference_refs(
    schema_obj: dict,
    *,
    full_schema: Optional[dict] = None,
    skip_keys: Optional[Sequence[str]] = None,
) -> dict:
    """Try to substitute $refs in JSON Schema."""

    full_schema = full_schema or schema_obj
    skip_keys = (
        skip_keys
        if skip_keys is not None
        else _infer_skip_keys(schema_obj, full_schema)
    )
    return _dereference_refs_helper(schema_obj, full_schema, skip_keys)

@dataclass(frozen=True)
class ReducedOpenAPISpec:
    """A reduced OpenAPI spec.

    This is reduced representation for OpenAPI specs.

    Attributes:
        servers: The servers in the spec.
        description: The description of the spec.
        endpoints: The endpoints in the spec.
    """

    servers: List[dict]
    description: str
    endpoints: List[Tuple[str, str, dict]]


def reduce_openapi_spec(url: str, spec: dict) -> ReducedOpenAPISpec:
    """Simplify OpenAPI spec to only required information for the agent"""

    # 1. Consider only GET and POST
    endpoints = [
        (route, docs.get("description"), docs)
        for route, operation in spec["paths"].items()
        for operation_name, docs in operation.items()
        if operation_name in ["get", "post"]
    ]

    # 2. Replace any refs so that complete docs are retrieved.
    # Note: probably want to do this post-retrieval, it blows up the size of the spec.
    endpoints = [
        (name, description, dereference_refs(docs, full_schema=spec))
        for name, description, docs in endpoints
    ]

    # 3. Strip docs down to required request args + happy path response.
    def reduce_endpoint_docs(docs: dict) -> dict:
        out = {}
        if docs.get("summary"):
            out["summary"] = docs.get("summary")
        if docs.get("operationId"):
            out["operationId"] = docs.get("operationId")
        if docs.get("description"):
            out["description"] = docs.get("description")
        if docs.get("parameters"):
            out["parameters"] = [
                parameter
                for parameter in docs.get("parameters", [])
                if parameter.get("required")
            ]
        if "200" in docs["responses"]:
            out["responses"] = docs["responses"]["200"]
        if docs.get("requestBody"):
            out["requestBody"] = docs.get("requestBody")
        return out

    endpoints = [
        (name, description, reduce_endpoint_docs(docs))
        for name, description, docs in endpoints
    ]

    return ReducedOpenAPISpec(
        servers=[{
                'url': url,
            }
        ],
        description=spec["info"].get("description", ""),
        endpoints=endpoints,
    )


def get_required_param_descriptions(endpoint_spec: dict) -> str:
    """Get an OpenAPI endpoint required parameter descriptions"""
    descriptions = []

    schema = (
        endpoint_spec.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    properties = schema.get("properties", {})

    required_fields = schema.get("required", [])

    for key, value in properties.items():
        if "description" in value:
            if value.get("required") or key in required_fields:
                descriptions.append(value.get("description"))

    return ", ".join(descriptions)

def ensure_openapi_path(url: str) -> str:
    if url.endswith('/openapi.json'):
        return url
    elif url.endswith('/'):
        return f'{url}openapi.json'
    else:
        return f'{url}/openapi.json'