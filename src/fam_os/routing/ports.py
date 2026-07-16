"""Port implemented by task-routing policies."""

from typing import Protocol

from fam_os.routing.contracts import RoutingRequest, RoutingResult


class TaskRouter(Protocol):
    def route(self, request: RoutingRequest) -> RoutingResult: ...


class RoutingTextEmbedder(Protocol):
    def embed(self, embedding_space_id: str, text: str) -> tuple[float, ...]: ...
