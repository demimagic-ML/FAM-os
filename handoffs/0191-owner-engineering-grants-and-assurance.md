# Handoff 0191: Owner engineering grants and assurance

**Date:** 2026-07-18  
**Plan step:** Phase 24.6–24.9 and Phase 24 exit gate  
**Status:** Phase 24 complete at contract and component-test maturity  
**Previous handoff:** `0190-engineering-authority-integration-surfaces.md`

## Objective

Complete the owner-sovereignty boundary for engineering authority with visible
profiles, bounded and revocable grants, exact-consequence break-glass approval,
and assurance labels that cannot be elevated by authority.

## Scope completed

- Added safe-default, workspace-operator, engineering-administrator, custom,
  and full-owner delegation expansion with no hidden master boolean.
- Added target-, time-, purpose-, workspace-, path-, toolchain-, network-,
  registry-, Git-, secret-, resource-, reversibility-, and verification-bound
  engineering grant contracts.
- Defaulted inheritance off and prohibited inheritance for high-risk grants.
- Added action, changeset, task, and session grant scopes plus active, revoked,
  and consumed lifecycle states.
- Added authenticated grant approvals bound to canonical grant digests.
- Added exact-consequence break-glass challenges and decisions for exceptional
  authority and verification waiver.
- Added a deterministic fake-driven grant ledger covering admission,
  authorization, scope/budget rejection, revocation, expiry, and consumption.
- Added `verified`, `executed_unverified`, and `verification_waived` execution
  assurance plus Shell/Console projection.
- Added seven strict schema roots and cross-document grant/approval/challenge/
  authorization/execution validation.
- Proved the Phase 24 exit condition with forged prompt, repository, model, and
  tool approval sources.

## Explicitly not completed

- The grant ledger is a component-test implementation, not a durable production
  repository or restart-safe authorization service.
- No OS, filesystem, shell, package, network, design, Git, production,
  administrator, secret, policy, or self-update effect uses these grants yet.
- No real owner authentication adapter or installed break-glass UI was added.
- No Phase 25 repository planner work is included.
- Phase 21.7 and Phase 23 remain unchanged.

## Architecture and decisions

ADR 0167 makes owner authentication a trusted Core port and separates it from
all untrusted content channels. Grant admission is digest-bound; authorization
then checks only admitted live state and exact request scope. Break-glass is a
second independently verified ceremony. Assurance derives solely from verifier
evidence or a recorded waiver, never from grant breadth.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/delegation.py` | Visible delegation profiles and exact expansion. |
| `src/fam_os/core/engineering/grants.py` | Grant, scope, resource, approval, and authorization contracts. |
| `src/fam_os/core/engineering/break_glass.py` | Exceptional consequence challenge and decision contracts. |
| `src/fam_os/core/engineering/grant_policy.py` | Fake-driven authenticated grant lifecycle and authorization. |
| `src/fam_os/core/engineering/assurance.py` | Truthful execution assurance records and classifier. |
| `src/fam_os/core/engineering/results.py` | Adds the engineering execution discriminator. |
| `src/fam_os/core/engineering/__init__.py` | Exports the completed Phase 24 contract surface. |
| `src/fam_os/schemas/catalog.py` | Registers seven grant and assurance roots. |
| `src/fam_os/schemas/references.py` | Validates grant lifecycle cross-references. |
| `schemas/v1alpha1/fam.core.*.schema.json` | Adds generated grant/assurance schemas. |
| `src/fam_os/shell/engineering_projection.py` | Renders exact execution assurance. |
| `src/fam_os/console/static/task_updates.js` | Labels verified, unverified, and waived execution. |
| `tests/contract/schema_engineering_fixtures.py` | Supplies grant lifecycle schema documents. |
| `tests/unit/test_engineering_grant_lifecycle.py` | Proves delegation, grant, break-glass, revocation, and exit behavior. |
| `tests/unit/test_shell_engineering_projection.py` | Proves assurance presentation. |
| `tests/unit/test_console_task_updates.py` | Proves Console assurance labels. |
| `docs/decisions/0167-owner-authentication-admits-engineering-grants.md` | Records the owner-authenticated grant model. |
| `MASTER_PLANv2.md` | Marks Phase 24.6–24.9 and the exit evidence complete. |

## Public interfaces

- `EngineeringDelegationMode`, `expand_delegation`
- `EngineeringAuthorityGrant`, `EngineeringGrantScope`,
  `EngineeringResourceImpact`, and their policy enums
- `OwnerGrantApproval`, `EngineeringAuthorizationRequest`, and
  `EngineeringAuthorizationDecision`
- `BreakGlassChallenge`, `BreakGlassDecision`, and `consequences_digest`
- `OwnerAuthorityVerifier`, `EngineeringGrantLedger`, and
  `engineering_grant_digest`
- `EngineeringExecutionAssurance`, `EngineeringExecutionRecord`, and
  `classify_execution_assurance`
- Seven new exact-alpha schemas; 309 generated schemas total

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_contracts \
  tests.unit.test_engineering_grant_lifecycle \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references \
  tests.unit.test_action_intent_firewall \
  tests.unit.test_packaged_runtime_catalog \
  tests.unit.test_shell_engineering_projection \
  tests.unit.test_console_task_updates \
  tests.contract.test_integration_coverage
```

Result: 89 tests passed.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
git diff --check -- <Phase 24 source, configuration, tests, and documentation>
```

Result: all 309 generated schemas validated and the whitespace check passed.

The complete-suite host dependency limitation remains recorded in Handoff 0188
and was not misreported as a Phase 24 regression or a green suite.

## Evidence and artifacts

- `docs/decisions/0167-owner-authentication-admits-engineering-grants.md`
- `tests/unit/test_engineering_grant_lifecycle.py`
- `schemas/v1alpha1/fam.core.engineering-grant.schema.json`
- `schemas/v1alpha1/fam.core.engineering-execution.schema.json`

## Known limitations and risks

- The ledger is volatile and must not be used as production authorization until
  Phase 25+ work adds encrypted persistence, restart reconciliation, replay
  protection, and a real owner-authentication adapter.
- Path matching uses bounded `PurePosixPath.match` policy and needs dedicated
  provider-specific canonicalization before filesystem effects.
- Break-glass consequence text is digest-bound but needs an installed owner UI
  that renders and authenticates the exact bytes.
- An execution record references evidence; production policy must resolve those
  IDs to trusted immutable verifier and effect records.

## Operational notes

No services, packages, models, credentials, external repositories, or
operating-system state were changed.

## Recommended next entry point

Start Phase 25.1 with Core-owned repository planning over existing workspace
map/retrieve capabilities. Read ADRs 0165–0167, Handoffs 0188–0191, and the
existing Phase 19 workspace contracts. Keep planning read-only until a Phase 24
grant has been admitted by a production owner-authentication boundary.
