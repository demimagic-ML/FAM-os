# Handoff 0158: Phase 22 plan and production failure discovery

**Date:** 2026-07-17  
**Plan step:** Phase 22.1  
**Status:** Partial  
**Previous handoff:** `0157-installed-console-application-failure-recovery.md`

## Objective

Audit the existing Expert Factory, research the real LoRA/QLoRA implementation
path and defensible sample quantities, write the production Phase 22 plan, and
replace the acceptance-only failure cluster with the first live production
boundary: signed, content-free, proposal-only verified-failure discovery.

## Scope completed

- Audited the Phase 13 token classifier, current production composition,
  terminal redaction, storage, schemas, worker budgets, Expert Fabric release
  path, and open Phase 22 coverage.
- Researched LoRA, QLoRA, TRL/PEFT/bitsandbytes, Qwen3-1.7B, LIMA, and current
  Blackwell bitsandbytes compatibility using primary project and paper sources.
- Added a detailed Phase 22 production plan with empirical sample checkpoints,
  split-before-synthesis, authority boundaries, worker isolation, evaluation,
  activation, rollback, and exit evidence.
- Corrected the Master Plan dependency wording so local Phase 22 work can proceed
  while the independent Phase 21.7 two-physical-host evidence gate remains open.
- Added strict production failure trace, cluster, and capability-proposal
  contracts with deterministic identities and digests.
- Added migration 0019 and an owner-private encrypted append-only discovery
  repository with restart-safe latest-proposal projection.
- Wired a supervised discovery service into the production verifier failure path.
  It accepts only failed runs from signed verifier packages, hashes the rejected
  candidate, persists no prompt, candidate, fact, or verifier feedback, and
  cannot affect inference completion.
- Added three generated schemas and focused contract, storage, restart,
  encryption, observer, and gateway tests.

## Explicitly not completed

- Training-content capture grants and revocation.
- Provenance-bound source staging, split assignment, teacher generation, and
  per-example deterministic or human verification.
- Any training approval, CUDA worker, LoRA/QLoRA training, evaluation,
  conversion, signed specialist installation, activation, rollback, or removal.
- Installed signed-release evidence for the new discovery service.
- Phase 21.7 physical multi-device qualification.

## Architecture and decisions

ADR 0139 preserves terminal redaction: Phase 20 learning records remain
content-free and cannot be mined back into a dataset. Factory content will use a
separate explicit expiring grant. Source families must be assigned to partitions
before synthesis, descendants inherit the partition, and held-out content is
never visible to teachers or training workers.

The new discovery contracts do not replace the Phase 13 `FailureTrace` types;
they use a separate production schema version so historical acceptance evidence
remains stable. A Core observer protocol keeps Core independent of the product
factory implementation. Observer exceptions are logged and advisory; they never
change verification or final-result policy.

## Files changed

| Path | Purpose |
|---|---|
| `docs/architecture/PHASE22_REAL_EXPERT_FACTORY.md` | Detailed production Phase 22 implementation and evidence plan |
| `docs/decisions/0139-training-content-requires-explicit-authority-and-split-before-synthesis.md` | Content authority and leakage boundary |
| `src/fam_os/expert_factory/failure_discovery.py` | Strict production discovery contracts and deterministic clustering |
| `src/fam_os/product/factory_discovery.py` | Supervised signed-verifier failure observer |
| `src/fam_os/product/storage/factory_discovery_repository.py` | Encrypted append-only discovery persistence |
| `src/fam_os/product/storage/migrations/0019_factory_failure_discovery.sql` | Discovery tables and indexes |
| `src/fam_os/core/production/verification.py` | Failure observer protocol |
| `src/fam_os/core/production/verification_flow.py` | Advisory observer call after deterministic failure |
| `src/fam_os/core/production/execution_worker.py` | Observer composition boundary |
| `src/fam_os/core/production/gateway.py` | Gateway injection boundary |
| `src/fam_os/product/service.py` | Start and stop the production discovery service |
| `src/fam_os/product/composition/core_storage.py` | Discovery repository composition |
| `src/fam_os/schemas/catalog.py` | Three production discovery schemas |
| `tests/unit/test_factory_failure_discovery.py` | Contract, encryption, restart, and proposal tests |
| `tests/unit/test_production_task_gateway.py` | Core observer integration regression |
| `tests/unit/test_production_database.py` | Migration 0019 table and restart contract |
| `tests/contract/schema_manifest_fixtures.py` | Representative schema round trips |
| `MASTER_PLAN.md` | Phase execution point and 22.1 partial evidence |
| `configs/integration/coverage.json` | Factory maturity and remaining gaps |

## Public interfaces

Added serialized roots:

- `fam.factory.verified-failure-trace/v1alpha1`
- `fam.factory.verified-failure-cluster/v1alpha1`
- `fam.factory.capability-proposal/v1alpha1`

No user command or HTTP endpoint was added yet. Discovery is internally live in
the composed product, but overall Expert Factory production reachability remains
false until the governed dataset and training workflow is user-reachable.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest \
  tests.unit.test_factory_failure_discovery \
  tests.unit.test_production_database \
  tests.unit.test_production_task_gateway \
  tests.contract.test_schema_roundtrip -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --output schemas
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
.verification-venv/bin/ruff check \
  src/fam_os/expert_factory/failure_discovery.py \
  src/fam_os/product/factory_discovery.py \
  src/fam_os/product/storage/factory_discovery_repository.py \
  src/fam_os/core/production/verification_flow.py \
  tests/unit/test_factory_failure_discovery.py
```

Result: 32 focused tests passed, all 245 registered schemas rendered and
validated, and affected lint passed.

## Evidence and artifacts

- ADR: `docs/decisions/0139-training-content-requires-explicit-authority-and-split-before-synthesis.md`
- Plan: `docs/architecture/PHASE22_REAL_EXPERT_FACTORY.md`
- Schemas: `schemas/v1alpha1/fam.factory.verified-failure-*.schema.json` and
  `schemas/v1alpha1/fam.factory.capability-proposal.schema.json`
- No installed or training artifact is claimed by this partial step.

## Known limitations and risks

- Source-checkout verifier packages have `local_unverified` trust and correctly
  produce no factory trace; a signed installed release is required for live data.
- The current family key is capability, acceptance requirement, and verifier.
  Later dataset construction must add source-family provenance and semantic
  subfamilies without changing historical traces.
- Candidate hashes can support evidence binding, not content recovery. This is
  intentional and means prospective opt-in capture is required.
- The service has no user-visible proposal view yet.

## Operational notes

Opening an existing product database applies migration 0019. All new payloads
are encrypted by the existing owner-bound product cipher. Stopping the product
stops the observer before storage closes. No model was downloaded or trained.

## Recommended next entry point

Continue Phase 22.1 with `src/fam_os/expert_factory/` and
`src/fam_os/product/storage/`: add the expiring confirmed capture grant,
provenance-bound source contracts, deterministic split assignment before
synthesis, a bounded teacher interface, per-example verification, encrypted
storage, and Shell/Console proposal visibility. Do not mark 22.1 complete until
an installed signed run proves that path without weakening terminal redaction.
