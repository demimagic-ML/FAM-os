"""Application provider projection for bounded deterministic Linux adapters."""

from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.linux import ScopedFileAdapter
from fam_os.applications import ObservationResult, ObservationStatus


class DeterministicFileProvider:
    def __init__(self, entry, adapter: ScopedFileAdapter):
        self.entry = entry
        self.adapter = adapter

    def capability(self, instance_id, capability_id):
        if (instance_id, capability_id) != (
            self.entry.instance_id, self.entry.capability_id,
        ):
            return None
        return self.entry

    def observe(self, request):
        if request.resource_uri is None or not request.resource_uri.startswith("file:"):
            raise ValueError("deterministic file observation requires a file URI")
        include = request.parameters.get("include_content", False)
        if not isinstance(include, bool) or set(request.parameters) != {"include_content"}:
            raise ValueError("deterministic file parameters are invalid")
        observed = self.adapter.observe(Path(request.resource_uri[7:]), include)
        payload = {
            "size_bytes": observed.size_bytes,
            "sha256": observed.sha256,
            "content": (
                observed.content.decode("utf-8") if observed.content is not None else None
            ),
        }
        return ObservationResult(
            request.request_id, ObservationStatus.OBSERVED,
            datetime.now(timezone.utc), payload,
            request.resource_uri, f"sha256:{observed.sha256}",
        )
