"""Deterministic Draft 2020-12 schema generation from domain dataclasses."""

from __future__ import annotations

from dataclasses import MISSING, fields
from datetime import datetime
from enum import Enum
from typing import ForwardRef

from fam_os.schemas.descriptor import SchemaDescriptor
from fam_os.schemas.type_support import (
    annotation_args,
    is_domain_dataclass,
    is_enum,
    is_mapping,
    is_tuple,
    is_union,
    type_hints,
)


JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BASE_URI = "https://schemas.fam-os.local/"


def build_schema(descriptor: SchemaDescriptor) -> dict[str, object]:
    builder = _SchemaBuilder()
    payload = builder.for_type(descriptor.root_type)
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"{SCHEMA_BASE_URI}{descriptor.schema_id}.schema.json",
        "title": descriptor.title,
        "type": "object",
        "required": ["schema_id", "contract_version", "payload"],
        "properties": {
            "schema_id": {"const": descriptor.schema_id},
            "contract_version": {"const": descriptor.contract_version},
            "payload": payload,
        },
        "additionalProperties": False,
        "$defs": builder.definitions,
    }


class _SchemaBuilder:
    def __init__(self) -> None:
        self.definitions: dict[str, object] = {}
        self._types: dict[str, type[object]] = {}
        self._uses_json_value = False

    def for_type(self, annotation: object) -> dict[str, object]:
        if annotation is type(None):
            return {"type": "null"}
        if annotation is str:
            return {"type": "string"}
        if annotation is bool:
            return {"type": "boolean"}
        if annotation is int:
            return {"type": "integer"}
        if annotation is float:
            return {"type": "number"}
        if annotation is datetime:
            return {"type": "string", "format": "date-time"}
        if is_enum(annotation):
            return self._enum_schema(annotation)
        if is_domain_dataclass(annotation):
            return self._dataclass_ref(annotation)
        if is_union(annotation):
            return {"anyOf": [self.for_type(item) for item in annotation_args(annotation)]}
        if is_tuple(annotation):
            item_type = annotation_args(annotation)[0]
            return {"type": "array", "items": self.for_type(item_type)}
        if is_mapping(annotation):
            return {"type": "object", "additionalProperties": self._json_value_ref()}
        if isinstance(annotation, ForwardRef):
            return self._json_value_ref()
        raise TypeError(f"unsupported schema annotation: {annotation!r}")

    def _enum_schema(self, enum_type: type[Enum]) -> dict[str, object]:
        return {"type": "string", "enum": [item.value for item in enum_type]}

    def _dataclass_ref(self, value_type: type[object]) -> dict[str, object]:
        name = value_type.__name__
        previous = self._types.get(name)
        if previous is not None and previous is not value_type:
            raise TypeError(f"duplicate schema definition name: {name}")
        if name not in self.definitions:
            self._types[name] = value_type
            self.definitions[name] = {}
            self.definitions[name] = self._dataclass_schema(value_type)
        return {"$ref": f"#/$defs/{name}"}

    def _dataclass_schema(self, value_type: type[object]) -> dict[str, object]:
        hints = type_hints(value_type)
        properties: dict[str, object] = {}
        required: list[str] = []
        for field in fields(value_type):
            field_schema = self.for_type(hints[field.name])
            if field.name == "contract_version" and field.default is not MISSING:
                field_schema = {"const": field.default}
            properties[field.name] = field_schema
            required.append(field.name)
        return {
            "type": "object",
            "required": required,
            "properties": properties,
            "additionalProperties": False,
        }

    def _json_value_ref(self) -> dict[str, object]:
        if not self._uses_json_value:
            self._uses_json_value = True
            self.definitions["JsonValue"] = {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string"},
                    {"type": "integer"},
                    {"type": "number"},
                    {"type": "boolean"},
                    {"type": "array", "items": {"$ref": "#/$defs/JsonValue"}},
                    {
                        "type": "object",
                        "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                    },
                ]
            }
        return {"$ref": "#/$defs/JsonValue"}
