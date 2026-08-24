# Handoff 0250: Automatic governed documentation regeneration

**Date:** 2026-07-19  
**Plan step:** Phase 30.1, 30.5, 30.6, 30.7, and 30.9  
**Status:** Partial (`source_composed`)  
**Previous handoff:** `0249-bounded-candidate-repair-and-final-state-changesets.md`

## Objective

Allow documentation-bearing natural tasks to repair code and regenerate all
governed outputs safely, with digest-bound governance, a persisted requirement
decision, and real code/test/evidence traceability.

## Scope completed

- Added a policy-selection receipt binding exact required generated-content
  kinds to durable intent and candidate identity, including an explicit empty
  conclusion when no generated artifact is required.
- Added Core-rehashed governance bindings for ownership, authoritative
  regeneration, and a repository requirement anchor.
- The requirement anchor records task and acceptance digests while excluding
  the raw owner prompt and private/credential data.
- Included source and governance digests in generation request identity.
- A verification-driven code repair now reruns signed documentation generation
  before the repaired candidate is verified.
- Old stale requests, bindings, receipts, and reports remain append-only; apply
  passes only when each governed output has at least one exact current receipt.
- Staleness report and trace retries are deterministic and do not conflict on
  changed observation timestamps.
- Automatically records a satisfied or explicitly partial requirement trace
  over real changed implementation paths, test paths, and passing candidate
  verification evidence.
- Extended encrypted storage, schemas, Console, and Shell read-only document
  unions for selection and governance-binding records.
- The real repair integration now changes code and its test twice, regenerates
  the API reference after the failed intermediate version, preserves one stale
  and one current report, creates a satisfied trace, reaches one exact
  checkpoint, applies, reverifies, and commits successfully.

## Explicitly not completed

- Signed-installed or live production-verifier proof of this source branch.
- An independently delayed incident recovery observation beyond the final
  repaired verification set.
- Remaining independent-review selection/remediation/waiver governance.
- Phase 27/29 specialized powers, both-profile qualification, 24-hour soak, and
  independent human security review.

## Architecture and decisions

ADR 0215 keeps generator adapters as authority-free signed byte producers.
Core owns requirement selection, governance hashing, receipt supersession,
staleness admission, and trace assurance. Historical records are never edited;
current candidate bytes decide which receipt is active.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/documentation.py` | Selection and governance-binding contracts. |
| `src/fam_os/core/engineering/documentation_policy.py` | Requirement-anchor path. |
| `src/fam_os/core/engineering/documentation_service.py` | Governance-aware staleness comparison. |
| `src/fam_os/product/engineering_documentation_api.py` | Rehash admission, current-receipt selection, and trusted trace evidence. |
| `src/fam_os/product/natural_engineering_documentation.py` | Persist selection, generate governance anchors, and regenerate by current digests. |
| `src/fam_os/product/natural_engineering_trace.py` | Deterministic trace construction. |
| `src/fam_os/product/natural_engineering_repair.py` | Regeneration callback before repaired verification. |
| `src/fam_os/product/natural_engineering_execution.py` | Documentation repair and trace orchestration. |
| `src/fam_os/adapters/sqlite/engineering_documentation.py` | Immutable selection and binding storage. |
| `src/fam_os/product/service.py` | Owner-bound codec composition. |
| `src/fam_os/shell/engineering_loop_contracts.py` | Read-only typed Shell union. |
| `src/fam_os/schemas/catalog.py` | Two new public schemas. |
| `tests/integration/test_natural_engineering_incident.py` | Real repair/regeneration/trace/apply proof. |
| `tests/unit/test_product_engineering_documentation_api.py` | Policy binding, governance drift, replay, and encryption tests. |

## Public interfaces

- `DocumentationRequirementSelection`
- `DocumentationGovernanceBinding`
- `DOCUMENTATION_REQUIREMENTS_PATH`
- `ProductEngineeringLoopApi.record_documentation_selection(...)`
- Natural engineering checkpoint responses may include
  `requirement_traces`.
- Shell/Console documentation queries now return selection and governance
  records alongside requests, receipts, reports, and traces.

## Validation

```bash
larry run env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_documentation_recipes \
  tests.unit.test_governed_documentation \
  tests.unit.test_product_engineering_documentation_api \
  tests.unit.test_candidate_generation_service \
  tests.unit.test_candidate_changeset_service \
  tests.unit.test_candidate_squash \
  tests.unit.test_candidate_workspace \
  tests.unit.test_candidate_verification_service \
  tests.unit.test_engineering_diagnostic_redaction \
  tests.unit.test_runtime_diagnostics \
  tests.unit.test_engineering_execution \
  tests.unit.test_natural_engineering_execution \
  tests.unit.test_engineering_incident_service \
  tests.unit.test_local_git_delivery_service \
  tests.unit.test_product_engineering_loop_api \
  tests.unit.test_product_natural_engineering_api \
  tests.unit.test_fam_shell_natural_engineering \
  tests.unit.test_fam_shell_engineering_loop_transport \
  tests.integration.test_natural_engineering_incident \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_natural_engineering_publication \
  tests.integration.test_console_natural_engineering \
  tests.integration.test_console_engineering_loop \
  tests.integration.test_product_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references \
  tests.security.test_engineering_adversarial
```

Result: 150 tests passed. Raw log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T10-30-03-879Z.log`.

```bash
larry run env PYTHONPATH=src:. python3 -m unittest discover \
  -s tests/architecture -t .
```

Result: 41 architecture tests passed. Raw log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T10-30-30-257Z.log`.

```bash
larry run env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Result: all 410 schemas rendered and validated; JavaScript syntax and diff
whitespace checks passed. Schema log:
`/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM/FAM_OS/runs/run-2026-07-19T10-30-30-249Z.log`.

## Evidence and artifacts

- ADR 0215
- The source validation logs above
- Real temporary Git repository assertions in
  `tests/integration/test_natural_engineering_incident.py`

## Known limitations and risks

- A pending pre-ADR generated receipt has no trustworthy generation-time
  governance digest and therefore fails closed after upgrade.
- Requirement traces are truthful: repositories without an affected test path
  receive `partial`, not an invented satisfied trace.
- Signed candidate `phase30-governance-20260719-3` predates this branch.

## Operational notes

No live service, active release, owner repository outside tests, remote, or
host policy was changed. Temporary test repositories were removed.

## Recommended next entry point

Finish Phase 30.8 with deterministic review selection, independently produced
signed or human checkpoints, typed remediation resolution, and an exact owner
waiver ceremony. Then build the next integrated signed candidate containing
both repaired and rollback incident branches plus governed regeneration.
