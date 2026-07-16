"""Shared annotation and JSON-value support for schema codecs."""

from __future__ import annotations

import math
import sys
from collections.abc import Mapping
from dataclasses import is_dataclass
from enum import Enum
from types import UnionType
from typing import ForwardRef, Union, get_args, get_origin, get_type_hints

from fam_os.applications import payloads


def type_hints(value_type: type[object]) -> dict[str, object]:
    module_globals = vars(sys.modules[value_type.__module__])
    namespace = {**module_globals, **vars(payloads)}
    return get_type_hints(value_type, globalns=namespace)


def is_union(annotation: object) -> bool:
    return get_origin(annotation) in (UnionType, Union)


def is_mapping(annotation: object) -> bool:
    origin = get_origin(annotation)
    return origin is not None and issubclass(origin, Mapping)


def is_tuple(annotation: object) -> bool:
    return get_origin(annotation) is tuple


def is_enum(annotation: object) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, Enum)


def is_domain_dataclass(annotation: object) -> bool:
    return isinstance(annotation, type) and is_dataclass(annotation)


def annotation_args(annotation: object) -> tuple[object, ...]:
    return get_args(annotation)


def validate_json_value(value: object, path: str = "$") -> object:
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"invalid object key at {path}")
            result[key] = validate_json_value(item, f"{path}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [validate_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise ValueError(f"unsupported JSON value at {path}")


JSON_VALUE_FORWARD_TYPES = (ForwardRef,)
