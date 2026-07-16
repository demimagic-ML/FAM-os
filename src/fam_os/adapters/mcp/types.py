"""Small adapter-owned values normalized from MCP SDK objects."""

from dataclasses import dataclass, field
from typing import Mapping

from fam_os.applications.payloads import JsonObject, freeze_payload


@dataclass(frozen=True, slots=True)
class McpServerInfo:
    name: str
    version: str
    protocol_version: str

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.name, self.version, self.protocol_version)):
            raise ValueError("MCP server information must not be empty")


@dataclass(frozen=True, slots=True)
class McpResource:
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None

    def __post_init__(self) -> None:
        if not self.uri.strip() or not self.name.strip():
            raise ValueError("MCP resource URI and name must not be empty")


@dataclass(frozen=True, slots=True)
class McpTool:
    name: str
    description: str | None
    input_schema: JsonObject
    output_schema: JsonObject | None = None
    annotations: JsonObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("MCP tool name must not be empty")
        object.__setattr__(self, "input_schema", freeze_payload(self.input_schema))
        if self.output_schema is not None:
            object.__setattr__(self, "output_schema", freeze_payload(self.output_schema))
        object.__setattr__(self, "annotations", freeze_payload(self.annotations))


@dataclass(frozen=True, slots=True)
class McpResourcePage:
    items: tuple[McpResource, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class McpToolPage:
    items: tuple[McpTool, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class McpReadResult:
    contents: tuple[JsonObject, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contents", tuple(freeze_payload(item) for item in self.contents)
        )


@dataclass(frozen=True, slots=True)
class McpCallResult:
    is_error: bool
    content: tuple[JsonObject, ...]
    structured_content: JsonObject | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "content", tuple(freeze_payload(item) for item in self.content)
        )
        if self.structured_content is not None:
            object.__setattr__(
                self, "structured_content", freeze_payload(self.structured_content)
            )


@dataclass(frozen=True, slots=True)
class McpDiscoverySnapshot:
    server: McpServerInfo
    resources: tuple[McpResource, ...]
    tools: tuple[McpTool, ...]


def mutable_json(value):
    if isinstance(value, Mapping):
        return {key: mutable_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [mutable_json(item) for item in value]
    return value
