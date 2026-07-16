# ADR 0005: One Ollama adapter behind the inference-runtime port

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The parent RNF prototype contains three overlapping Ollama HTTP clients. Chat payload construction, timing, response parsing, loaded-model inspection, unload operations, prompts, routing, experiment policy, and report dictionaries are repeated or mixed across benchmark, expert-experiment, and orchestration modules.

FAM_OS needs one inference boundary that preserves the proven non-streaming lifecycle and telemetry without making Core depend on Ollama endpoints or JSON fields.

## Decision

`InferenceRuntime` remains the provider-neutral Core port. The `adapters/ollama` package implements it using:

- Explicit validated `OllamaSettings` supplied by the composition root.
- An injectable `JsonTransport` with a standard-library HTTP implementation.
- Pure request-payload translation.
- Pure provider-response parsing.
- A small `OllamaRuntime` lifecycle adapter for chat, loaded-model inspection, and unload.
- Provider-specific transport and protocol exceptions.

The port carries context length, maximum output, keep-alive intent, JSON-output intent, temperature, and optional seed. Prompts and route/expert policy remain caller-owned. The Phase 1 adapter requests final content with Ollama thinking output disabled and does not expose hidden reasoning content.

Ollama nanosecond durations are converted to seconds at the adapter boundary. Token counts, load time, wall time, and generation rate become `InferenceMetrics`. Loaded-model provider fields become typed resident bytes, accelerator bytes, and context tokens.

## Consequences

- Ollama URLs, endpoints, JSON shapes, and timing units exist only in the adapter.
- Core can be tested with an in-memory `InferenceRuntime` and no HTTP server.
- A future llama.cpp or remote runtime can implement the same lifecycle contract.
- Adapter tests use synthetic responses; the opt-in hardware test exercises the real local runtime.
- Streaming, embeddings, multimodal messages, tool-call schemas, authentication, and reasoning traces are not part of this Phase 1 contract.
- Service startup, cgroup enforcement, and runtime placement remain supervisor and scheduler responsibilities.

## Alternatives considered

1. Reuse one parent private HTTP helper: rejected because FAM_OS would import prototype implementation and untyped provider dictionaries.
2. Put HTTP calls in Core orchestration: rejected because provider details would leak across every use case.
3. Adopt a third-party Ollama client immediately: rejected because the required Phase 1 surface is small, the standard library is sufficient, and an additional dependency would not remove the need for our own contracts.
4. Implement streaming first: deferred until request/event contracts define cancellation, partial output, backpressure, and verification-safe release.

## Evidence

- Unit tests cover payloads, telemetry conversion, loaded models, unload, endpoint selection, transport failures, and invalid protocol shapes.
- A live local Granite chat passed through `OllamaRuntime`, produced typed telemetry, and was unloaded afterward.
- Graph-augmented search confirms FAM_OS source contains Ollama HTTP paths only in `adapters/ollama` and no parent RNF imports.

