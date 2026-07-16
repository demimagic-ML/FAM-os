#!/usr/bin/env python3
"""Build deterministic Phase 10.4 relevance-gate evidence."""

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.memory import MemoryAccessContext, MemoryScope
from fam_os.memory.relevance import MemoryRelevancePolicy, MemoryRetrievalCandidate


def main():
    now = datetime(2026, 7, 16, tzinfo=UTC)
    scope = MemoryScope("owner", ("assist",), workspace_ids=("FAM_OS",))
    values = (
        MemoryRetrievalCandidate("selected", scope, now, .95, 60),
        MemoryRetrievalCandidate("overflow", scope, now, .8, 50),
        MemoryRetrievalCandidate("low", scope, now, .2, 10),
        MemoryRetrievalCandidate("stale", scope, now - timedelta(days=8), .9, 10),
        MemoryRetrievalCandidate("denied", MemoryScope("other", ("assist",)), now, .99, 10),
    )
    decision = MemoryRelevancePolicy(.6, timedelta(days=7), 100).decide(
        values, MemoryAccessContext("owner", "assist", workspace_id="FAM_OS"), now,
    )
    output = Path(__file__).parents[1] / "artifacts/memory/phase10.4/relevance-gate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(decision), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
