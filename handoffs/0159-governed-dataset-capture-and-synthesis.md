# Handoff 0159: Governed dataset capture and synthesis

**Date:** 2026-07-17  
**Plan step:** Phase 22.1  
**Status:** Partial  
**Previous handoff:** `0158-phase22-plan-and-production-failure-discovery.md`

## Objective

Complete the source implementation of prospective opt-in content capture,
deterministic partition assignment before synthesis, bounded local teacher
generation, independent per-example review, encrypted restart-safe staging, and
owner-visible content-free discovery.

## Scope completed

- Added strict split policy, capture grant, revocation, captured source,
  synthetic proposal, and independent review contracts.
- Required a confirmed expiring grant binding an existing capability proposal,
  source kinds, workspaces, sensitivities, bytes, examples, and revision without
  granting training authority.
- Assigned source families to train, validation, or held-out before synthesis;
  descendants inherit their source partition.
- Rejected held-out generation before invoking a teacher or reviewer.
- Added a bounded local Ollama teacher with strict JSON and a separate
  deterministic review adapter.
- Added migration 0020 plus separate encrypted grant and staging repositories.
- Enforced revision, expiry, revocation, scope, sensitivity, source kind, byte,
  and example limits transactionally before insertion.
- Composed the dataset service into the product and added authenticated read-only
  Console APIs for traces, clusters, and proposals.
- Added six schemas and focused encryption, restart, lineage, held-out denial,
  revocation, budget, Console authentication, and composition tests.

## Explicitly not completed

- Shell or Console mutation controls for grant creation, source capture,
  generation, and revocation.
- A signed installed run proving an actual verifier failure through capture and
  teacher generation.
- Dataset sealing, exact/near deduplication, leakage reporting, held-out key
  isolation, and learning-curve manifests from Phase 22.4.
- Phase 22.2 training approval or any QLoRA worker, scheduling, evaluation,
  conversion, activation, rollback, or retirement.

## Architecture and decisions

ADR 0139 remains controlling. Phase 20 terminal history stays content-free;
training content enters only prospectively under a distinct grant. Split
assignment hashes a versioned seed and stable source-family identity. Generated
variants cannot cross partitions. Teacher and reviewer are separate ports, and
an accepted review creates only an accepted projection—it does not mutate the
proposal or authorize training.

The grant lifecycle and content staging repositories are separate bounded
modules. Content bytes use the existing owner-bound product cipher. Grant state
and counters are checked inside the same immediate transaction as insertion.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/expert_factory/dataset_provenance.py` | Grant, split, source, proposal, and review contracts |
| `src/fam_os/expert_factory/synthetic_generation.py` | Teacher and reviewer ports |
| `src/fam_os/product/factory_datasets.py` | Governed capture and generation service |
| `src/fam_os/product/factory_teacher.py` | Strict local Ollama teacher and reviewer adapters |
| `src/fam_os/product/storage/capture_grant_repository.py` | Revision-bound grant lifecycle |
| `src/fam_os/product/storage/dataset_staging_repository.py` | Bounded encrypted content staging |
| `src/fam_os/product/storage/migrations/0020_factory_dataset_staging.sql` | Grant, source, example, and review tables |
| `src/fam_os/console/factory_routes.py` | Authenticated content-free discovery APIs |
| `src/fam_os/console/http.py` | Factory API composition |
| `src/fam_os/product/service.py` | Dataset service and split policy composition |
| `src/fam_os/product/composition/core_storage.py` | Grant and staging repositories |
| `src/fam_os/schemas/catalog.py` | Six dataset provenance schemas |
| `tests/unit/test_factory_dataset_provenance.py` | Capture, lineage, encryption, restart, held-out, revocation, and bounds |
| `tests/integration/test_console_factory.py` | Authenticated discovery API |
| `tests/unit/test_production_database.py` | Migration 0020 contract |
| `tests/contract/schema_manifest_fixtures.py` | New schema round trips |

## Public interfaces

Added serialized roots:

- `fam.factory.dataset-split-policy/v1alpha1`
- `fam.factory.training-capture-grant/v1alpha1`
- `fam.factory.training-capture-revocation/v1alpha1`
- `fam.factory.captured-dataset-source/v1alpha1`
- `fam.factory.synthetic-example-proposal/v1alpha1`
- `fam.factory.synthetic-example-review/v1alpha1`

Added authenticated Console GET endpoints:

- `/api/v1/factory/traces`
- `/api/v1/factory/clusters`
- `/api/v1/factory/proposals`

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check src tests tools
PYTHONPATH=src:. .verification-venv/bin/mypy --follow-imports=skip \
  src/fam_os/expert_factory/dataset_provenance.py \
  src/fam_os/expert_factory/failure_discovery.py \
  src/fam_os/product/factory_datasets.py \
  src/fam_os/product/factory_teacher.py \
  src/fam_os/product/factory_discovery.py \
  src/fam_os/product/storage/capture_grant_repository.py \
  src/fam_os/product/storage/dataset_staging_repository.py \
  src/fam_os/product/storage/factory_discovery_repository.py
PYTHONPATH=src:. .verification-venv/bin/python \
  tools/render_contract_schemas.py --check --output schemas
```

Result: 1,074 tests passed with two declared environment skips. Full Ruff and
affected Mypy passed. All 251 schemas validated. Larry indexed 2,003 files and
5,328 symbols.

## Evidence and artifacts

- Full suite log:
  `~/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-17T17-21-51-863Z.log`
- Schemas: `schemas/v1alpha1/fam.factory.*.schema.json`
- No installed, dataset-seal, teacher-quality, or training artifact is claimed.

## Known limitations and risks

- Capture and generation lack an owner-facing mutation command, so 22.1 remains
  in progress and overall factory production reachability remains false.
- SQLite staging is bounded and encrypted, but Phase 22.4 still needs immutable
  blob manifests, deduplication, leakage reports, and held-out key isolation.
- Teacher output is always untrusted; every accepted example still needs
  independent evidence.
- Enough independent source families are needed to populate every partition;
  families must never be moved after synthesis to repair counts.

## Operational notes

Opening an existing product database applies migration 0020. No new daemon,
port, model download, or background generation starts automatically. Teacher
generation occurs only after a valid grant and explicit caller action.

## Recommended next entry point

Finish owner-facing capture/generation controls and signed installed 22.1
evidence, then implement Phase 22.2 as a separate bounded approval service. One
immutable approval must bind capability, sealed dataset, base/tokenizer revision
and license, training recipe, resource budget, runtime/output bounds, environment
digest, expiry, confirmation, and one-use job identity. Any changed field needs
a new approval.
