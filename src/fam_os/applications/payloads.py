"""Immutable JSON-compatible payloads at connector boundaries."""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping, TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]
JsonObject: TypeAlias = Mapping[str, JsonValue]


def freeze_payload(payload: Mapping[str, object] | None = None) -> JsonObject:
    source = {} if payload is None else payload
    return _freeze_mapping(source)


def _freeze_mapping(value: Mapping[object, object]) -> JsonObject:
    items: dict[str, JsonValue] = {}
    for key in sorted(value, key=str):
        if not isinstance(key, str) or not key:
            raise ValueError("payload keys must be non-empty strings")
        items[key] = _freeze_value(value[key])
    return MappingProxyType(items)


def _freeze_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("payload floats must be finite")
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    raise ValueError(f"payload value has unsupported type: {type(value).__name__}")
