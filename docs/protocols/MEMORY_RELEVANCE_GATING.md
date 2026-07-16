# Memory relevance gating

Phase 10.4 applies deterministic gates after retrieval and before model context assembly.

1. Exact owner, purpose, application, workspace, and session scope.
2. Maximum record age.
3. Minimum normalized relevance score.
4. Hard total context-token budget.

Eligible candidates are ordered by descending relevance and stable record ID. A candidate that would exceed the remaining token budget is rejected rather than truncated silently. Every rejection carries one exact reason code: `memory.scope-denied`, `memory.stale`, `memory.low-relevance`, or `memory.context-budget`.

The policy has no model dependency and no authority to widen scope. Phase 10.4 evidence exercises all four rejection paths and selects only one eligible record.
