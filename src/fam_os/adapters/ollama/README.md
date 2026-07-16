# Ollama adapter ownership

This package implements the provider-neutral `InferenceRuntime` port using Ollama's local HTTP API.

It owns endpoint paths, JSON payloads, provider response parsing, transport errors, and conversion of Ollama nanosecond timing fields into FAM telemetry. It does not own prompts, routing, expert selection, repair, escalation, verification, reporting, service lifecycle, or cgroup policy.

Phase 1 supports non-streaming chat, loaded-model inspection, and confirmed unload. Ollama may acknowledge `keep_alive=0` before `/api/ps` removes the model, so this adapter polls within a bounded timeout and raises unless absence is confirmed. Confirmed absence is an activation barrier; cgroup telemetry is still required because it does not prove that every allocator or file-cache byte was immediately reclaimed.

Streaming and richer runtime capabilities require later contract work.

Phase 7.2 adds read-only `/api/show` context-profile observation. Ollama metadata
is translated into provider-neutral architecture dimensions; conservative
fallbacks remain explicit assumptions. Estimation policy and arithmetic stay in
the scheduler. See `docs/protocols/CONTEXT_MEMORY_ESTIMATION.md` and ADR 0059.
