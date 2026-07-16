"""SDK-neutral MCP ingress tool and result values."""

from dataclasses import dataclass

from fam_os.applications.payloads import JsonObject, freeze_payload


@dataclass(frozen=True, slots=True)
class McpIngressTool:
    name: str
    capability_id: str
    title: str
    description: str
    input_schema: JsonObject
    output_schema: JsonObject

    def __post_init__(self) -> None:
        for name in ("name", "capability_id", "title", "description"):
            if not getattr(self, name).strip():
                raise ValueError(f"MCP ingress {name} must not be empty")
        object.__setattr__(self, "input_schema", freeze_payload(self.input_schema))
        object.__setattr__(self, "output_schema", freeze_payload(self.output_schema))


@dataclass(frozen=True, slots=True)
class McpIngressOutcome:
    is_error: bool
    safe_message: str
    structured_content: JsonObject

    def __post_init__(self) -> None:
        if not self.safe_message.strip():
            raise ValueError("MCP ingress safe message must not be empty")
        object.__setattr__(
            self, "structured_content", freeze_payload(self.structured_content)
        )
