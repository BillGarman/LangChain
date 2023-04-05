"""Pydantic models for parsing an OpenAPI spec."""

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Type, Union

from openapi_schema_pydantic import Parameter, Reference, Schema
from pydantic import BaseModel, Field

from langchain.tools.openapi.utils.openapi_utils import HTTPVerb, OpenAPISpec

PRIMITIVE_TYPES = {
    "integer": int,
    "number": float,
    "string": str,
    "boolean": bool,
    "array": List,
    "object": Dict,
    "date-time": str,
    "null": None,
}

# See https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.1.0.md#parameterIn
# for more info.
class APIPropertyLocation(Enum):
    """The location of the property."""

    QUERY = "query"
    PATH = "path"
    HEADER = "header"
    COOKIE = "cookie"  # Not yet supported

    @classmethod
    def from_str(cls, location: str) -> "APIPropertyLocation":
        """Parse an APIPropertyLocation."""
        try:
            return cls(location)
        except ValueError:
            raise ValueError(
                f"Invalid APIPropertyLocation. Valid values are {cls.__members__}"
            )


SUPPORTED_LOCATIONS = {
    APIPropertyLocation.QUERY,
    APIPropertyLocation.PATH,
}

SCHEMA_TYPE = Union[str, Type, tuple, None, Enum]


class APIPropertyBase(BaseModel):
    """Base model for an API property."""

    # The name of the parameter is required and is case sensitive.
    # If "in" is "path", the "name" field must correspond to a template expression
    # within the path field in the Paths Object.
    # If "in" is "header" and the "name" field is "Accept", "Content-Type",
    # or "Authorization", the parameter definition is ignored.
    # For all other cases, the "name" corresponds to the parameter
    # name used by the "in" property.
    name: str = Field(alias="name")
    """The name of the property."""

    required: bool = Field(alias="required")
    """Whether the property is required."""

    type: SCHEMA_TYPE = Field(alias="type")
    """The type of the property.
    
    Either a primitive type, a component/parameter type,
    or an array or 'object' (dict) of the above."""

    default: Optional[Any] = Field(alias="default", default=None)
    """The default value of the property."""

    description: Optional[str] = Field(alias="description", default=None)
    """The description of the property."""


class APIProperty(APIPropertyBase):
    """A model for a property in the query, path, header, or cookie params."""

    location: APIPropertyLocation = Field(alias="location")
    """The path/how it's being passed to the endpoint."""

    @staticmethod
    def _cast_schema_list_type(schema: Schema) -> Optional[Union[str, tuple]]:
        type_ = schema.type

        if not isinstance(type_, list):
            return type_
        else:
            return tuple(type_)

    @staticmethod
    def _get_schema_type(parameter: Parameter, schema: Schema) -> SCHEMA_TYPE:
        # TODO: recurse and differentiate between union vs. intersection types
        schema_type: SCHEMA_TYPE = APIProperty._cast_schema_list_type(schema)
        if schema_type == "array":
            items = schema.items
            if isinstance(items, Reference):
                ref_name = items.ref.split("/")[-1]
                schema_type = f'"{ref_name}"'  # To be valid typescript
            elif isinstance(items, Schema):
                schema_type = APIProperty._cast_schema_list_type(items)
            else:
                raise ValueError(f"Unsupported array items: {items}")
            if isinstance(schema_type, str):
                # TODO: recurse
                schema_type = (schema_type,)
        elif schema_type == "object":
            # TODO: Resolve array and object types to components.
            raise NotImplementedError(f"Objects not yet supported")
        elif schema_type in PRIMITIVE_TYPES:
            if schema.enum:
                param_name = f"{parameter.name}Enum"
                return Enum(param_name, schema.enum)
            else:
                pass
        else:
            raise NotImplementedError(f"Unsupported type: {schema_type}")
        return schema_type

    @classmethod
    def from_parameter(cls, parameter: Parameter, spec: OpenAPISpec) -> "APIProperty":
        """Instantiate from an OpenAPI Parameter."""
        # TODO: Resolve array and object types to components.
        location = APIPropertyLocation.from_str(parameter.param_in)
        if location not in SUPPORTED_LOCATIONS:
            raise NotImplementedError(
                f"Unsupported APIPropertyLocation. Valid values are {SUPPORTED_LOCATIONS}"
            )
        if parameter.content:
            raise ValueError(
                "API Properties with media content not supported. Media content only supported within APIRequestBodyProperty's"
            )
        schema = parameter.param_schema
        if isinstance(schema, Reference):
            schema = spec.get_referenced_schema(schema)
        if not isinstance(schema, Schema):
            raise ValueError(f"Error dereferencing schema: {schema}")
        schema_type = cls._get_schema_type(parameter, schema)
        default_val = schema.default if schema is not None else None
        return cls(
            name=parameter.name,
            location=location,
            default=default_val,
            description=parameter.description,
            required=parameter.required,
            type=schema_type,
        )


class APIRequestBodyProperty(APIPropertyBase):
    """A model for a request body property."""

    properties: List[APIProperty] = Field(alias="properties")
    """The sub-properties of the property."""


class APIRequestBody(BaseModel):
    """A model for a request body."""

    properties: List[APIRequestBodyProperty] = Field(alias="properties")

    # E.g., application/json - we only support JSON at the moment.
    media_type: str = Field(alias="media_type")
    """The media type of the request body."""


class APIOperation(BaseModel):
    """A model for a single API operation."""

    operation_id: str = Field(alias="operation_id")
    """The unique identifier of the operation."""

    description: str = Field(alias="description")
    """The description of the operation."""

    base_url: str = Field(alias="base_url")
    """The base URL of the operation."""

    path: str = Field(alias="path")
    """The path of the operation."""

    method: HTTPVerb = Field(alias="method")
    """The HTTP method of the operation."""

    properties: Sequence[APIProperty] = Field(alias="properties")

    # TODO: Add parse in used components to be able to specify what type of
    # referenced object it is.
    # """The properties of the operation."""
    # components: Dict[str, BaseModel] = Field(alias="components")

    # request_body: Optional[APIRequestBody] = Field(alias="request_body")
    # """The request body of the operation."""

    @classmethod
    def from_openapi_url(
        cls,
        spec_url: str,
        path: str,
        method: str,
    ) -> "APIOperation":
        """Create an APIOperation from an OpenAPI URL."""
        spec = OpenAPISpec.from_url(spec_url)
        return cls.from_openapi_spec(spec, path, method)

    @classmethod
    def from_openapi_spec(
        cls,
        spec: OpenAPISpec,
        path: str,
        method: str,
    ) -> "APIOperation":
        """Create an APIOperation from an OpenAPI spec."""
        operation = spec.get_operation(path, method)
        parameters = spec.get_parameters_for_operation(operation)
        properties = [APIProperty.from_parameter(param, spec) for param in parameters]
        return cls(
            operation_id=operation.operationId,
            description=operation.description,
            base_url=spec.base_url,
            path=path,
            method=method,
            properties=properties,
        )

    @staticmethod
    def ts_type_from_python(type_: SCHEMA_TYPE) -> str:
        if type_ is None:
            return "null"
        elif isinstance(type_, str):
            return {
                "str": "string",
                "integer": "number",
                "float": "number",
                "date-time": "string",
            }.get(type_, type_)
        elif isinstance(type_, tuple):
            return f"Array<{APIOperation.ts_type_from_python(type_[0])}>"
        elif isinstance(type_, type) and issubclass(type_, Enum):
            return " | ".join([f"'{e.value}'" for e in type_])
        else:
            return str(type_)

    def to_typescript(self) -> str:
        """Get typescript string representation of the operation."""
        operation_name = self.operation_id
        params = []

        for prop in self.properties:
            prop_name = prop.name
            prop_type = self.ts_type_from_python(prop.type)
            prop_required = "" if prop.required else "?"
            prop_desc = f"/* {prop.description} */" if prop.description else ""
            params.append(f"{prop_desc}\n\t\t{prop_name}{prop_required}: {prop_type},")

        formatted_params = "\n".join(params).strip()
        typescript_definition = f"""
// {self.description}
type {operation_name} = (_: {{
{formatted_params}
}}) => any;
"""
        return typescript_definition.strip()
