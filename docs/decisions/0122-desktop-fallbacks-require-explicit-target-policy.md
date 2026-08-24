# ADR 0122: Desktop fallbacks require explicit target policy

**Status:** Accepted  
**Date:** 2026-07-17

## Context

FAM_OS already had bounded AT-SPI and active-window X11 adapters, but they were
component-level bridges. Starting them automatically whenever a desktop backend
was present would turn environmental discovery into observation or input
authority. It would also hide the privacy difference between semantic
accessibility data and captured pixels.

The production Application Fabric needs these bridges for applications without
native, MCP, or deterministic tool interfaces, while retaining the integration
ladder and fail-closed action verification.

## Decision

The product service owns a `ProductFallbacks` lifecycle behind an owner-private
versioned `fallbacks.json` policy. Absence means both mechanisms are disabled.
Enabling a mechanism requires explicit privacy acknowledgement and one or more
exact process or process/window targets. Unknown fields, duplicate identities,
unbounded lists, non-private files, and action-without-observation combinations
are rejected.

Observation and action are configured separately. Observation-only policy
registers no action capability. Requested screen action degrades to observation
only when the input backend is unavailable. Every registered action remains
irreversible and always-confirmed, with an explicit primitive allowlist.

The lifecycle registers the bridges as local Application Fabric transports.
They still pass through normal capability lookup, permission grants, proposal
binding, confirmation, replay protection, audit, and final-result policy.
Accessibility object fingerprints and screen scenes are revalidated before the
provider is invoked. Core then makes a new observation and matches the claimed
poststate; provider evidence alone never verifies the action.

FAM Console exposes the configured/active state, privacy impact, target scopes,
action primitives, confirmation behavior, and degradation reason through an
authenticated integrations endpoint and a dedicated Applications surface.

## Consequences

- Desktop support cannot silently expand FAM_OS authority.
- Exact process/window targets may need owner updates after applications
  restart; automatic authority migration is intentionally not performed.
- Native connectors and deterministic tools remain preferred because fallback
  state is costlier and less semantically precise.
- AT-SPI availability does not expose protected text, and screen input cannot
  bypass incompatible Wayland sessions.
- A successful provider call can still fail the Core action when independent
  re-observation differs or is unavailable.
