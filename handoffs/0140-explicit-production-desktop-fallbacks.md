# Handoff 0140: Explicit production desktop fallbacks

**Date:** 2026-07-17  
**Plan step:** Phase 19.7  
**Status:** Complete  
**Previous handoff:** `0139-permission-filtered-production-mcp-ingress.md`

## Scope completed

- Added a strict versioned `fallbacks.json` contract and schema. The file must
  be owner-controlled and mode 0600; absence disables both mechanisms.
- Required explicit privacy acknowledgement and exact connector, instance,
  process, and window targets. No discovered desktop application silently
  becomes an authorized fallback target.
- Composed bounded AT-SPI and active-window X11 bridges as local transports in
  the production Application Fabric lifecycle.
- Separated observation from action configuration. Observation-only policy
  registers no action capability; unavailable X11 input degrades to screen
  observation without input authority.
- Preserved accessibility protected-text redaction, object fingerprint
  revalidation, action allowlists, bounded screen PNG capture, exact focused
  window/scene checks, and input primitive/key allowlists.
- Kept every fallback action irreversible and always-confirmed in the registry.
- Activated independent Core postconditions for accessibility and screen
  actions. Core makes a fresh observation and compares the claimed fingerprint
  or scene rather than trusting provider output.
- Added an authenticated `GET /api/v1/integrations` endpoint and a Console
  Applications surface showing disabled/active/degraded state, privacy impact,
  exact scopes, action primitives, and confirmation behavior.
- Added an operator guide and ADR 0122 documenting the authority boundary and
  deliberate lack of automatic target migration.

## Validation

- The complete repository suite passes: 923 tests, two declared skips.
- All 39 architecture boundary tests pass.
- Focused fallback, verifier, Console, adapter, provider, and service tests pass
  as a 31-test slice.
- Tests prove default-off behavior, private and exact configuration, privacy
  acknowledgement, unknown-field rejection, schema closure, observation-only
  degradation, real transport observation/action, cleanup, and independent
  postcondition failure on mismatched re-observation.
- Product service tests prove the new lifecycle starts and stops safely when no
  fallback policy is present.
- Full Ruff passes. Mypy passes for the seven affected production modules.
- The Console JavaScript passes syntax checking and the changed tree passes
  whitespace validation.

## Operational boundary

Configured process and X11 window IDs are exact and can become stale after an
application restarts. The owner must update the private policy; FAM_OS does not
move authority to a newly discovered process. Enabling a fallback does not
create a Core permission grant or bypass proposal, confirmation, replay, audit,
verification, or final-result policy.

## Next entry point

Continue Phase 19.10. Bundle the declared open-license Console fonts, implement
the direct undo/reversal interaction, close SSE replay/disconnect/terminal edge
coverage, and then run the Phase 19 exit scenario from a fresh signed install
against a live VS Code instance.
