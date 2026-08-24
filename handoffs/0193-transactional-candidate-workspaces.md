# Handoff 0193: Transactional candidate workspaces

**Date:** 2026-07-18  
**Plan step:** Phase 26.1–26.7  
**Status:** Complete  
**Previous handoff:** `0192-bounded-repository-intelligence-and-architecture.md`

## Objective

Create and verify complete multi-file changes away from the owner's checkout,
then reconcile an approved baseline-bound transaction without overwriting stale
or concurrent owner state.

## Scope completed

- Added strict candidate artifact, baseline, operation, preview, receipt, and
  self-update-protection contracts and six canonical schema roots.
- Added reflink-first isolated candidate creation with safe full-copy fallback,
  bounded regular-file handling, and whole-tree symlink rejection.
- Added typed directory create, file create/patch/restore, move/rename, delete,
  and executable-bit operations.
- Preserved text/binary kind, MIME type, bounded metadata, provenance, source
  name, size, and SHA-256 identity for staged artifacts.
- Added bounded text diffs, binary asset summaries, risk codes, verification
  evidence IDs, and rollback scope to one approval-ready preview.
- Added shell-free allowlisted verification rooted in the candidate workspace.
- Added full preflight, durable journal and backups, atomic per-path writes,
  interruption recovery, completed-changeset restoration, and owner-change
  preservation.
- Added a self-update policy that allows only declared source checkout paths and
  denies runtime, trust, active release, live policy, and unrelated paths.

## Explicitly not completed

- Candidate workspace effects are not wired into the signed installed Core
  gateway and therefore are not production-reachable.
- Phase 27's signed polyglot recipe catalog, transient sandbox matrix,
  dependency resolution, SBOM, and vulnerability evidence remain open.
- No claim of impossible multi-path atomic visibility is made; the guarantee is
  atomic per-path replacement plus durable all-or-scoped-rollback recovery.

## Architecture and decisions

ADR 0169 keeps transaction policy and public contracts in Core while concrete
filesystem cloning, MIME/diff rendering, process transport, journaling, and
reconciliation stay behind adapters. Candidate work happens outside the owner
workspace. Recovery owns only a recorded FAM_OS post-state; a mismatching path
is preserved as an owner change and the receipt reports `recovery_required`.

Source self-edit permission is intentionally separate from the existing signed
release manager. Source changes must still traverse build, verification,
signature, health check, activation, and rollback before becoming active.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/transactions.py` | Candidate and self-update contracts |
| `src/fam_os/core/engineering/__init__.py` | Public Core exports |
| `src/fam_os/adapters/filesystem/candidate_io.py` | No-symlink bounded clone and atomic I/O |
| `src/fam_os/adapters/filesystem/candidate_preview.py` | Text and binary preview rendering |
| `src/fam_os/adapters/filesystem/candidate_workspace.py` | Candidate lifecycle and reconciliation |
| `src/fam_os/adapters/filesystem/candidate_verification.py` | Candidate-rooted bounded verification |
| `src/fam_os/adapters/filesystem/__init__.py` | Adapter exports |
| `src/fam_os/schemas/catalog.py` | Six public schema registrations |
| `src/fam_os/schemas/references.py` | Candidate cross-document validation |
| `schemas/v1alpha1/fam.core.candidate-*.schema.json` | Canonical candidate schemas |
| `schemas/v1alpha1/fam.core.engineering-self-update-policy.schema.json` | Canonical source protection schema |
| `tests/unit/test_candidate_workspace.py` | Exit, conflict, interruption, and restore tests |
| `tests/contract/schema_transaction_fixtures.py` | Representative strict documents |
| `tests/contract/test_schema_roundtrip.py` | Candidate schema round trips |
| `tests/contract/test_schema_compatibility.py` | Strict/future-version rejection |
| `tests/contract/test_cross_contract_references.py` | Candidate reference coverage |
| `docs/decisions/0169-candidate-workspaces-reconcile-through-owned-journals.md` | Durable transaction decision |
| `MASTER_PLANv2.md` | Phase 26 status and evidence |
| `configs/integration/coverage.json` | Truthful component maturity |

## Public interfaces

- `CandidateArtifact`, `CandidateArtifactMetadata`, `CandidateBaselineEntry`
- `CandidateWorkspace`, `CandidateOperation`, `CandidateOperationKind`
- `CandidatePreviewItem`, `CandidateTransactionPreview`
- `CandidateApplyReceipt`, `CandidateApplyStatus`
- `EngineeringSelfUpdatePolicy`
- `CandidateWorkspaceAdapter`
- `CandidateVerificationAdapter`, `CandidateVerificationEvidence`
- Six `fam.core.* /v1alpha1` document roots for the public Core contracts

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_candidate_workspace tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility tests.contract.test_cross_contract_references -v
PYTHONPATH=src python3 tools/render_contract_schemas.py --check
python3 -m py_compile src/fam_os/core/engineering/transactions.py src/fam_os/adapters/filesystem/candidate_io.py src/fam_os/adapters/filesystem/candidate_preview.py src/fam_os/adapters/filesystem/candidate_workspace.py src/fam_os/adapters/filesystem/candidate_verification.py
git diff --check
```

Result: 40 focused unit/contract tests pass; 321 canonical schemas validate;
all new Python modules compile; diff whitespace validation passes. The earlier
full-suite host dependency failures remain recorded in handoff 0188 and were
not caused or changed by Phase 26.

## Evidence and artifacts

- `tests/unit/test_candidate_workspace.py`
- `docs/decisions/0169-candidate-workspaces-reconcile-through-owned-journals.md`
- `schemas/v1alpha1/fam.core.candidate-workspace.schema.json`
- `schemas/v1alpha1/fam.core.candidate-preview.schema.json`
- `schemas/v1alpha1/fam.core.candidate-apply-receipt.schema.json`

## Known limitations and risks

- Full-copy fallback can require workspace-sized storage.
- Transaction storage is owner-private local filesystem state, not yet an
  encrypted multi-process production repository.
- Readers may observe a transaction between per-path replacements.
- Candidate verification here proves isolation and bounded transport; Phase 27
  owns toolchain qualification and sandbox hardening.

## Operational notes

Candidate roots and journals are created only under the explicitly configured
transaction root. Do not place that root inside the owner workspace. A receipt
with `recovery_required` identifies paths preserved because their current state
no longer matched the FAM_OS-applied post-state; those paths require owner
review and must not be automatically overwritten.

## Recommended next entry point

Start Phase 27.1. Read `src/fam_os/core/engineering/tools.py`,
`src/fam_os/adapters/linux/bounded_command.py`, the existing verifier sandbox
adapters, ADR 0169, and this handoff. First define signed typed recipe and exact
raw-shell grant contracts without exposing a shell session to models.
