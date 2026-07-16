# Handoff 0049: Required application action safety

**Date:** 2026-07-16  
**Plan step:** Phase 5.11  
**Status:** Complete  
**Previous handoff:** `0048-restricted-screen-input-fallback.md`

## Objective

Implement one Core-owned authorization, verification, recovery, and audit
envelope for every Application Fabric action level so no adapter's invocation or
provider evidence can bypass the established release invariant.

## Scope completed

- Exact current plan revision, route, capability, instance, grant, resource,
  proposal, confirmation, principal, time, and prior-evidence validation.
- Required trusted precondition checks before provider invocation and trusted
  postcondition checks before verified release.
- Atomic confirmation execution reservation and audited replay rejection.
- At-most-once provider invocation with safe provider-exception mapping.
- Output withholding on invalid results, failed conditions, missing recovery
  metadata, and audit failure.
- Required recovery capability for reversible and compensatable proposals,
  opaque token preservation, and explicit compensation-required state.
- Content-free action request and terminal audit contracts with two strict
  schemas and canonical digest encoding.
- Private, user-owned, `O_NOFOLLOW`, append-locked, `fsync`-backed JSONL audit
  storage with duplicate rejection and SHA-256 chain verification.
- Lifecycle evidence for action results and audit records, with plan advancement
  only after required audit handling.
- One prepare-to-confirm-to-execute integration proof using the real Core
  lifecycle services and trusted condition seam.

## Explicitly not completed

- Automatic undo or compensation; recovery is a separate future permissioned
  action through the normal lifecycle.
- Packaged application-action verifier implementations, which remain Phase 8.7.
- Signed or externally anchored audit records, multi-user audit storage, or
  protection from deletion by the owning user.
- The cross-application user acceptance and resource measurement in Phase 5.12.

## Architecture and decisions

ADR 0049 requires every integration level to enter one Core execution service.
The service treats provider results as untrusted input, independently verifies
declared conditions, and requires durable privacy-bounded audit around mutation.
A missing request audit blocks the provider. A missing terminal audit after
possible mutation forces a withheld failure while preserving available recovery
metadata. Undo is not automatic because it is itself consequential.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/applications/action_audit.py` | Audit intent, record, stages, verification, and errors. |
| `src/fam_os/applications/action_audit_codec.py` | Canonical encoding, decoding, and digest binding. |
| `src/fam_os/applications/action_audit_ports.py` | Audit sink protocol. |
| `src/fam_os/applications/actions.py` | Recovery capability invariant for compensatable proposals. |
| `src/fam_os/adapters/audit/application_jsonl.py` | Durable local action-audit chain. |
| `src/fam_os/core/lifecycle/application_authorization.py` | Shared route, capability, scope, and grant checks. |
| `src/fam_os/core/lifecycle/action_execution_contracts.py` | Execution command, result, rejection, and recovery values. |
| `src/fam_os/core/lifecycle/action_execution_validation.py` | Exact mutation authorization and evidence binding. |
| `src/fam_os/core/lifecycle/action_execution_service.py` | Required execution, verification, audit, and lifecycle orchestration. |
| `src/fam_os/core/lifecycle/action_result_policy.py` | Safe verification, output, failure, and recovery policy. |
| `src/fam_os/core/lifecycle/action_audit_policy.py` | Content-free audit projection. |
| `src/fam_os/core/lifecycle/action_execution_registry.py` | Atomic execution replay registry. |
| `src/fam_os/core/lifecycle/contracts.py` | Action-result and action-audit plan evidence kinds. |
| `src/fam_os/schemas/catalog.py` | Two strict application action-audit roots. |
| `schemas/v1alpha1/` | Deterministically generated action-audit schemas. |
| `tests/unit/test_application_action_audit.py` | Audit contracts, codec, privacy, durability, and tamper tests. |
| `tests/unit/test_core_action_execution.py` | Authorization, verifier, failure, replay, audit, and recovery tests. |
| `tests/integration/test_application_action_safety_end_to_end.py` | Real Core prepare/confirm/execute/verify/audit flow. |
| `tests/architecture/test_core_action_execution_boundary.py` | Core/provider/audit dependency confinement. |
| `docs/protocols/APPLICATION_ACTION_SAFETY.md` | Canonical action-safety semantics. |
| `docs/decisions/0049-required-application-action-safety-envelope.md` | Durable shared-envelope decision. |

## Public interfaces

- `ApplicationActionExecutionService`, `ActionExecutionCommand`,
  `ActionExecutionResult`, `ActionExecutionRejection`, and
  `ActionRecoveryMetadata`.
- `ActionConditionVerifier`, `ApplicationActionProvider`,
  `ActionExecutionReplayRegistry`, and `InMemoryActionExecutionReplayRegistry`.
- `ApplicationActionAuditIntent`, `ApplicationActionAuditRecord`,
  `ApplicationActionAuditVerification`, and `ApplicationJsonlAuditSink`.
- Schemas `fam.application.action-audit-intent/v1alpha1` and
  `fam.application.action-audit-record/v1alpha1`.
- Plan evidence kinds `action_result` and `action_audit`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_application_permissions_actions tests.unit.test_application_action_audit tests.unit.test_core_action_execution tests.architecture.test_core_action_execution_boundary tests.integration.test_application_action_safety_end_to_end
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools connectors/vscode/test
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
python3 <AST module/function size gate>
cd connectors/vscode && npm test
larry index . && larry health .
```

Result: all 27 focused tests passed. Both Python environments passed all 546
tests with two expected environment-dependent skips each. All 42 serialized
schemas matched and compileall succeeded. All 299 Python implementation modules
remained at or below 300 lines per module and 50 lines per function. The native
connector passed seven Node tests, cross-language transport integration, and all
eight capability-schema validations. Larry indexed 754 files / 2,337 symbols
with 10,731 nodes / 40,086 edges and clean health; the persisted code graph was
refreshed to the same 10,731-node / 40,086-edge source view.

## Evidence and artifacts

- `docs/protocols/APPLICATION_ACTION_SAFETY.md`
- `docs/decisions/0049-required-application-action-safety-envelope.md`
- `tests/integration/test_application_action_safety_end_to_end.py`
- `schemas/v1alpha1/fam.application.action-audit-intent.schema.json`
- `schemas/v1alpha1/fam.application.action-audit-record.schema.json`

## Known limitations and risks

- Verification strength depends on the trusted condition implementation supplied
  to Core; Phase 8.7 must package and deploy concrete verifiers.
- The local hash chain reveals tampering but cannot prevent the owning user from
  truncating or deleting the audit file.
- A provider can mutate and fail before returning a recovery token; Core reports
  possible mutation but cannot invent recoverability.
- Recovery tokens are opaque and intentionally excluded from audit content.

## Operational notes

Tests used temporary audit directories and fake action providers only; no live
application was mutated. No services, sockets, or model processes were left
running. Existing VS Code connector output was rebuilt during validation.

## Recommended next entry point

Begin Phase 5.12. Read the Shell gateway/projection and transport, deterministic
file/tool adapters, Linux discovery/accessibility bridge, VS Code connector,
MCP client mapping, and the new action execution service. Compose a non-stub
vertical runner for README summarization, one bounded test, and a previewed
revision-bound file edit, then repeat with MCP unavailable and record per-level
context, reliability, latency, CPU, RAM, VRAM, and I/O evidence.
