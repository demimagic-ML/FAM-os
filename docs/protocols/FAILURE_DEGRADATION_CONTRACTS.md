# Failure and Degradation Contracts

## Contract family

Core-facing terminal failures and degradation notices use `fam.failure/v1alpha1`. Application Fabric keeps a smaller `fam.application.failure/v1alpha1` component-owned `ApplicationFailure` that Core can translate without importing Core policy into connector contracts.

These immutable Python contracts have strict serialized roots under the schema catalog. Unknown fields, versions, enums, and codes rejected by domain construction cannot cross the decoder boundary. See `SERIALIZED_SCHEMA_COMPATIBILITY.md` and ADR 0018.

## Failure envelope

`FailureEnvelope` carries only boundary-safe information:

- a correlation/error ID;
- a stable namespaced code;
- a broad category;
- the owning component;
- a bounded one-line safe message;
- retry disposition;
- optional capability identity;
- references to separately retained trusted evidence.

It contains no exception object, stack trace, command output, provider payload, prompt, secret, filesystem path, or raw connector session. Detailed failure evidence stays with the owning component and is linked by ID.

Categories distinguish invalid request, permission denial, unavailability, timeout, cancellation, resource exhaustion, incompatibility, provider failure, verification failure, postcondition failure, and internal failure. Retry policy is explicit rather than inferred from a provider exception. Permission denial can retry only after user action (or never), and cancellation cannot retry automatically.

## Application failure evidence

`ApplicationFailure` is owned by Application Fabric. Observation and action results no longer carry arbitrary error strings. They carry a namespaced code, safe message, retry disposition, category, and evidence references.

Result status and failure category must agree:

- denied results map to permission denial;
- unavailable observations map to unavailability;
- action precondition, execution, postcondition, and cancellation statuses map to the matching category.

This retains application-specific semantics without making Application Fabric depend on Core. Phase 4 maps accepted component failures into the final Core envelope.

## Degradation notice

A degradation is not silently treated as success or failure. `DegradationNotice` records stable identity, a namespaced reason code, kind, component, safe message, quality impact, continuation disposition, optional original/replacement capability IDs, and trusted evidence references.

Kinds cover fallback use, unavailable capability, resource constraint, reduced context, reduced quality, partial result, and stale data. A fallback names both different capability IDs. Context or quality reduction cannot claim zero impact. A disposition explicitly says continue, request confirmation, or withhold.

## Final-result invariants

`TaskResult` now enforces:

- failed results carry a structured failure;
- successful results carry no failure;
- failure and degradation evidence IDs are also linked by the result;
- final reason text exactly matches the selected safe message for a failed or degradation-withheld result;
- completed or verified results cannot carry a withholding degradation;
- degradation IDs are unique;
- existing verified-result evidence and content-release invariants remain in force.

The Phase 1 verified-code use case now emits structured verification failure, unsupported-route degradation, and sanitized generation/placement/configuration failures. Known internal exception types map to stable safe messages; `str(exception)` is no longer copied into the final result.

## Adapter boundary

Adapters may raise or record provider-specific errors internally. Before those failures reach Core, a component boundary must classify them and retain raw evidence in restricted telemetry or audit storage. Only safe codes, messages, policy, and evidence references cross into final results.
