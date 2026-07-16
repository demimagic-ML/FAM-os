"""Provider-neutral local client capability and invocation contracts."""

import re
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from fam_os.applications.payloads import JsonObject, freeze_payload


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")


@dataclass(frozen=True, slots=True)
class IngressCapability:
    capability_id: str
    display_name: str
    description: str
    input_schema: JsonObject
    output_schema: JsonObject
    verification_required: bool = True

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.capability_id):
            raise ValueError("ingress capability ID is invalid")
        if not self.display_name.strip() or not self.description.strip():
            raise ValueError("ingress capability text must not be empty")
        for name in ("input_schema", "output_schema"):
            schema = freeze_payload(getattr(self, name))
            Draft202012Validator.check_schema(_mutable(schema))
            object.__setattr__(self, name, schema)


@dataclass(frozen=True, slots=True)
class CoreIngressRequest:
    request_id: str
    capability_id: str
    parameters: JsonObject

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.request_id):
            raise ValueError("ingress request ID is invalid")
        if not _IDENTIFIER.fullmatch(self.capability_id):
            raise ValueError("ingress capability ID is invalid")
        object.__setattr__(self, "parameters", freeze_payload(self.parameters))


def _mutable(value):
    if hasattr(value, "items"):
        return {key: _mutable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_mutable(item) for item in value]
    return value
