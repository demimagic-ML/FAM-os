"""Content-safe raw evidence returned by deterministic Linux adapters."""

from dataclasses import dataclass, field

from fam_os.applications.payloads import JsonObject, freeze_payload


@dataclass(frozen=True, slots=True)
class DeterministicAdapterResult:
    capability_id: str
    succeeded: bool
    output: JsonObject = field(default_factory=dict)
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("deterministic capability ID must not be empty")
        object.__setattr__(self, "output", freeze_payload(self.output))
        if self.succeeded == (self.error_code is not None):
            raise ValueError("deterministic result success and error disagree")
