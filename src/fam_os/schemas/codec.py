"""Canonical JSON encoding and strict typed decoding for contract documents."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum

from jsonschema import Draft202012Validator, FormatChecker

from fam_os.schemas.catalog import descriptor_for_type
from fam_os.schemas.compatibility import require_compatible
from fam_os.schemas.descriptor import SchemaDescriptor
from fam_os.schemas.errors import SchemaEncodingError, SchemaValidationError
from fam_os.schemas.schema_builder import build_schema
from fam_os.schemas.type_support import (
    annotation_args,
    is_domain_dataclass,
    is_enum,
    is_mapping,
    is_tuple,
    is_union,
    type_hints,
    validate_json_value,
)


def encode_document(value: object) -> dict[str, object]:
    descriptor = descriptor_for_type(type(value))
    if descriptor is None:
        raise SchemaEncodingError("domain type has no registered document schema")
    payload = _encode_value(value, "$.payload")
    return {
        "schema_id": descriptor.schema_id,
        "contract_version": descriptor.contract_version,
        "payload": payload,
    }


def dumps_document(value: object) -> str:
    return json.dumps(
        encode_document(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_document(document: Mapping[str, object]) -> object:
    schema_id, contract_version = _envelope_identity(document)
    descriptor = require_compatible(schema_id, contract_version)
    validate_document(document, descriptor)
    try:
        return _decode_value(document["payload"], descriptor.root_type, "$.payload")
    except SchemaValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise SchemaValidationError("domain invariant validation failed") from error


def loads_document(serialized: str) -> object:
    try:
        document = json.loads(serialized, parse_constant=_reject_json_constant)
    except (TypeError, json.JSONDecodeError, ValueError) as error:
        raise SchemaValidationError("document is not strict JSON", keyword="json") from error
    if not isinstance(document, Mapping):
        raise SchemaValidationError("document envelope must be an object", keyword="type")
    return decode_document(document)


def validate_document(document: Mapping[str, object], descriptor: SchemaDescriptor) -> None:
    validator = Draft202012Validator(build_schema(descriptor), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: tuple(item.absolute_path))
    if not errors:
        return
    error = errors[0]
    path = "$" + "".join(
        f"[{item}]" if isinstance(item, int) else f".{item}" for item in error.absolute_path
    )
    raise SchemaValidationError(
        f"schema validation failed at {path}",
        path=path,
        keyword=error.validator,
    )


def _envelope_identity(document: Mapping[str, object]) -> tuple[str, str]:
    schema_id = document.get("schema_id")
    contract_version = document.get("contract_version")
    if not isinstance(schema_id, str) or not schema_id.strip():
        raise SchemaValidationError("schema_id must be a non-empty string", path="$.schema_id")
    if not isinstance(contract_version, str) or not contract_version.strip():
        raise SchemaValidationError(
            "contract_version must be a non-empty string", path="$.contract_version"
        )
    return schema_id, contract_version


def _encode_value(value: object, path: str) -> object:
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise SchemaEncodingError(f"non-finite number at {path}")
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise SchemaEncodingError(f"timezone-naive datetime at {path}")
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _encode_value(getattr(value, field.name), f"{path}.{field.name}")
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        try:
            return validate_json_value(value, path)
        except ValueError as error:
            raise SchemaEncodingError("mapping contains a non-JSON value") from error
    if isinstance(value, (list, tuple)):
        return [_encode_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise SchemaEncodingError(f"unsupported value type at {path}")


def _decode_value(value: object, annotation: object, path: str) -> object:
    if annotation is type(None):
        if value is not None:
            raise SchemaValidationError("expected null", path=path, keyword="type")
        return None
    if annotation in (str, int, float, bool):
        return _decode_primitive(value, annotation, path)
    if annotation is datetime:
        return _decode_datetime(value, path)
    if is_enum(annotation):
        try:
            return annotation(value)
        except (TypeError, ValueError) as error:
            raise SchemaValidationError("unknown enum value", path=path, keyword="enum") from error
    if is_domain_dataclass(annotation):
        return _decode_dataclass(value, annotation, path)
    if is_union(annotation):
        return _decode_union(value, annotation_args(annotation), path)
    if is_tuple(annotation):
        if not isinstance(value, list):
            raise SchemaValidationError("expected array", path=path, keyword="type")
        item_type = annotation_args(annotation)[0]
        return tuple(_decode_value(item, item_type, f"{path}[{index}]") for index, item in enumerate(value))
    if is_mapping(annotation):
        if not isinstance(value, Mapping):
            raise SchemaValidationError("expected object", path=path, keyword="type")
        try:
            return validate_json_value(value, path)
        except ValueError as error:
            raise SchemaValidationError("invalid JSON payload", path=path) from error
    raise SchemaValidationError("unsupported target annotation", path=path)


def _decode_dataclass(value: object, value_type: type[object], path: str) -> object:
    if not isinstance(value, Mapping):
        raise SchemaValidationError("expected object", path=path, keyword="type")
    hints = type_hints(value_type)
    expected = {field.name for field in fields(value_type)}
    if set(value) != expected:
        raise SchemaValidationError("object fields do not match schema", path=path)
    kwargs = {
        name: _decode_value(value[name], annotation, f"{path}.{name}")
        for name, annotation in hints.items()
    }
    try:
        return value_type(**kwargs)
    except (TypeError, ValueError) as error:
        raise SchemaValidationError("domain invariant validation failed", path=path) from error


def _decode_union(value: object, choices: tuple[object, ...], path: str) -> object:
    for choice in choices:
        try:
            return _decode_value(value, choice, path)
        except SchemaValidationError:
            continue
    raise SchemaValidationError("value does not match any allowed type", path=path, keyword="anyOf")


def _decode_primitive(value: object, expected: type[object], path: str) -> object:
    if expected is float and type(value) in (int, float) and type(value) is not bool:
        number = float(value)
        if math.isfinite(number):
            return number
    elif type(value) is expected:
        return value
    raise SchemaValidationError("primitive type mismatch", path=path, keyword="type")


def _decode_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise SchemaValidationError("datetime must be a string", path=path, keyword="type")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SchemaValidationError("datetime has invalid format", path=path, keyword="format") from error
    if instant.tzinfo is None:
        raise SchemaValidationError("datetime must include a timezone", path=path, keyword="format")
    return instant


def _reject_json_constant(_: str) -> None:
    raise ValueError("non-finite JSON numbers are forbidden")
