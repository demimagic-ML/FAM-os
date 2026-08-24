# Handoff 0188: Typed engineering authority contracts

**Date:** 2026-07-18  
**Plan step:** Phase 24.1–24.3  
**Status:** Complete for steps 24.1–24.3; Phase 24 remains in progress  
**Previous handoff:** `0187-workspace-proposal-repair-and-escalation.md`

## Objective

Establish the inert, versioned Core contract boundary for owner-delegated
engineering powers before adding any broader filesystem, process, dependency,
design, Git, publication, or privileged runtime effect.

## Scope completed

- Added all eleven Phase 24.1 engineering document roots under
  `fam.core.engineering/v1alpha1`.
- Added the complete Phase 24.2 authority vocabulary, including every
  high-risk power that the owner may deliberately grant.
- Bound engineering tasks to owner/grant identity, intent, workspace roots,
  operations, path rules, toolchains, network and registry reach, budgets,
  expiry, Git scope, and checkpoint policy.
- Kept observation, proposal, modification, execution, network, publication,
  protected-reference writes, and other privileged effects separate.
- Added strict JSON schemas, representative round trips, exact-alpha
  compatibility checks, unknown-field rejection, domain invariants, and
  cross-document identity/reference validation.
- Added the additive v2 pointer to `MASTER_PLAN.md` without changing any Phase
  0–23 status.

## Explicitly not completed

- No new filesystem, process, shell, dependency, network, design, Git,
  publication, administrator, production, secret, policy, or self-update
  effect is runtime-reachable.
- Contracts do not prove that a grant is live, unexpired, or unrevoked; the
  Phase 24.6–24.8 grant lifecycle remains open.
- Engineering result kinds and truthful unverified/waived states remain Phase
  24.4 and 24.9 work.
- Action-intent recognition, signed expert scopes, Console/Shell projection,
  integration coverage, and the Phase 24 exit gate remain open.
- Phase 21.7 and Phase 23 gates are unchanged.

## Architecture and decisions

ADR 0165 places authority-bearing engineering admission records in Core and
keeps all concrete effects behind adapters. A model may propose typed data but
cannot create authority, hold a raw connector session, or execute inside the
deterministic supervisor. `RAW_SHELL` is owner-grantable but does not mean a
model receives a live shell; Core must still admit exact operations and route
them through an audited adapter.

## Files changed

| Path | Purpose |
|---|---|
| `MASTER_PLAN.md` | Points to the additive Phase 24+ plan. |
| `MASTER_PLANv2.md` | Records Phase 24.1–24.3 completion and evidence. |
| `src/fam_os/core/engineering/` | Engineering authority, task, workspace, tool, dependency, design, Git, checkpoint, and evidence contracts. |
| `src/fam_os/schemas/catalog.py` | Registers eleven engineering document roots. |
| `src/fam_os/schemas/references.py` | Validates engineering identities and cross-document links. |
| `schemas/v1alpha1/fam.core.*.schema.json` | Adds the eleven generated engineering schemas. |
| `tests/contract/schema_engineering_fixtures.py` | Supplies representative engineering documents. |
| `tests/contract/test_schema_roundtrip.py` | Includes every engineering root in exhaustive schema round trips. |
| `tests/contract/test_schema_compatibility.py` | Rejects future versions and unknown fields for every engineering root. |
| `tests/contract/test_cross_contract_references.py` | Checks task, snapshot, recipe, checkpoint, and evidence references. |
| `tests/unit/test_engineering_contracts.py` | Proves authority separation and key domain invariants. |
| `docs/decisions/0165-engineering-authority-is-typed-and-core-admitted.md` | Records the durable authority boundary. |

## Public interfaces

- `EngineeringTaskEnvelope`, `EngineeringAuthority`, `EngineeringOperation`,
  and `CheckpointPolicy`.
- `WorkspaceSnapshot`, `WorkspaceEntry`, `ChangeSetProposal`, `FileOperation`,
  and `FileOperationKind`.
- `ToolRecipe`, `ToolRun`, `ToolRunStatus`, `DependencyPlan`,
  `DependencyChange`, and `DependencyAction`.
- `DesignAssetManifest`, `DesignAsset`, `GitOperation`, and
  `GitOperationKind`.
- `CheckpointDecision`, `CheckpointDisposition`, `EngineeringEvidence`, and
  `EngineeringOutcome`.
- Eleven exact `fam.core.* /v1alpha1` schema families registered with contract
  version `fam.core.engineering/v1alpha1`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_contracts \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
```

Result: 37 tests passed.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
```

Result: all 297 generated schema artifacts validated.

```bash
larry run "PYTHONPATH=src:. python3 -m unittest discover -s tests"
```

Result: the source suite ran 1,416 tests and did not pass in this host Python
environment: 59 errors, one failure, and seven skips. The 59 errors share a
pre-existing dependency mismatch: installed `cryptography` certificate objects
do not provide `not_valid_before_utc`, while `pyproject.toml` requires a newer
version. The unrelated production-verifier binding test also returned a
non-verified result. Full log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-18T20-56-08-224Z.log`.

Ruff and Mypy could not run because neither module is installed in the current
host Python. No global or user package installation was performed.

## Evidence and artifacts

- `docs/decisions/0165-engineering-authority-is-typed-and-core-admitted.md`
- `schemas/v1alpha1/fam.core.engineering-task.schema.json`
- The full-suite Larry log listed above.

## Known limitations and risks

- The contract types are not yet connected to admission repositories, owner
  grant state, runtime providers, or product projections.
- The full suite needs a project-compatible isolated dependency environment
  before its result can be attributed to this change.
- Cross-document validation proves identity consistency for supplied records;
  it is not authorization and does not query live revocation state.

## Operational notes

No services, packages, credentials, system policies, repositories, or external
resources were changed. Schema rendering updated the repository's generated
schema set deterministically.

## Recommended next entry point

Continue with Phase 24.4. Read ADR 0165 and
`src/fam_os/core/engineering/evidence.py`, then add strict result/proposal and
receipt kinds that keep `verified`, `executed_unverified`,
`verification_waived`, publication, and unavailable outcomes unambiguous.
