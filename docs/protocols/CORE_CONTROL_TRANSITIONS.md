# Cancellation, timeout, and degradation transitions

Phase 4.7 adds replay-safe plan controls without provider calls. Cancellation
follows a declared `cancelled` edge. A trusted per-plan deadline may follow a
declared `unavailable` edge only when due. A typed `DegradationNotice` may also
follow `unavailable`; the immutable plan decides whether that leads to fallback,
confirmation, or withholding.

Every command matches request, route, opaque admission, instance, and expected
revision before its control ID is reserved. Missing edges never create implicit
fallback. Terminal states remain absorbing. Stale commands are rejected before
replay reservation.

Events store only control/degradation ID, kind, and an optional routed capability.
They do not store safe-message text, provider errors, prompts, or candidate
content. Degradation control ID must equal degradation ID so the evidence cannot
be replayed under a second control identity.

Timeout uses trusted `PlanDeadlinePolicy`, never a caller-supplied deadline.
State, deadlines, and replay registries remain in-memory. Timeout currently uses
the existing `unavailable` outcome while its evidence kind remains explicitly
`timeout`.
