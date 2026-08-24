# Handoff 0160: Real QLoRA backend and physical smoke

**Date:** 2026-07-17  
**Plan step:** Phase 22.1–22.5  
**Status:** Partial  
**Previous handoff:** `0159-governed-dataset-capture-and-synthesis.md`

## Objective

Complete the production source path from governed dataset sealing through exact
training approval, live resource admission, isolated QLoRA execution, durable
terminal evidence, and one non-promotable physical RTX 5080 smoke.

## Scope completed

- Added immutable canonical train, validation, and held-out blobs with encrypted
  write-once storage, exact/near deduplication, lineage, leakage, license, and
  sensitivity gates.
- Added one-use training approvals binding proposal, capability, dataset,
  licenses, sensitivities, model/tokenizer revisions, recipe, resources,
  environment, output bounds, expiry, and job identity.
- Resolved and installed a 77-wheel offline environment and downloaded the exact
  official Qwen3-1.7B revision with a 39-file manifest.
- Added environment, job, terminal, resource-snapshot, and admission contracts
  plus encrypted restart-safe repositories and atomic authority consumption.
- Added the real TRL/PEFT/bitsandbytes QLoRA worker, systemd cgroup and
  network-denied Bubblewrap boundary, live NVIDIA/resource monitoring, revocation
  and resource stops, structured safe errors, and independent parent-side
  adapter verification.
- Product-composed the backend behind explicit paths and authenticated Console
  probe/job/evidence routes.
- Ran five physical smokes. Attempts 01–04 failed closed and improved bounded
  sandbox diagnostics. Attempt 05 completed and passed every training safety
  invariant.
- Corrected the Console task watcher so a transient SSE/poll failure retries with
  bounded backoff instead of leaving a recoverable terminal task blinking.

## Explicitly not completed

- A promotable learning-curve dataset or held-out quality improvement.
- Phase 22.6 immutable candidate/incumbent evaluation.
- Phase 22.7 conversion, signing, disabled install, canary, or activation.
- Phase 22.8 rollback, retirement, artifact removal, or audit-retention proof.
- A signed installed repetition of 22.1–22.5; the smoke ran from the source tree.

## Architecture and decisions

ADR 0139 remains controlling. Dataset content is encrypted and prospectively
captured; ordinary terminal history remains redacted. The worker receives only
train/validation blobs, the exact base model, one recipe, and one writable output
directory. Held-out material, product state, signing keys, home, and network are
absent. A completed claim is accepted only when the parent recomputes the adapter
tree, adapter config, metrics, and size. Failed receipts may truthfully report
that isolation was never established; only completed receipts require positive
network-denial and held-out-absence evidence.

The training environment digest now includes the exact worker script as well as
Python, wheelhouse, packages, CUDA, driver, GPU, and capability facts. Changing
the worker therefore invalidates an old approval.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/expert_factory/dataset_sealing.py` | Immutable split and leakage contracts |
| `src/fam_os/product/storage/factory_dataset_blob_store.py` | Encrypted write-once partition blobs |
| `src/fam_os/product/factory_training_approvals.py` | Exact six-dimensional authority |
| `src/fam_os/expert_factory/training_backend.py` | Environment, job, and terminal contracts |
| `src/fam_os/expert_factory/resource_admission.py` | Hardware snapshot and admission decision |
| `src/fam_os/adapters/training/` | Environment probe, sandbox command, QLoRA worker, NVIDIA backend, resource observer |
| `src/fam_os/product/factory_training.py` | Admission, atomic consumption, execution, terminal persistence |
| `src/fam_os/product/composition/factory_training.py` | Optional production backend composition |
| `src/fam_os/product/service.py` | Dataset, approval, and real backend wiring |
| `src/fam_os/console/factory_routes.py` | Authenticated factory control and evidence API |
| `src/fam_os/product/storage/migrations/0021_factory_training_approvals.sql` | Training authority state |
| `src/fam_os/product/storage/migrations/0022_factory_sealed_datasets.sql` | Sealed data and blob receipts |
| `src/fam_os/product/storage/migrations/0023_factory_training_jobs.sql` | Environments, jobs, terminals |
| `src/fam_os/product/storage/migrations/0024_factory_training_admission.sql` | Resource and admission evidence |
| `configs/training/` | Exact Qwen3-1.7B QLoRA requirements and model revision |
| `tools/phase22_training_environment/` | Wheelhouse, offline install, and model download tooling |
| `tools/phase22_training_exit/` | Full physical smoke path and content-free evidence |
| `src/fam_os/console/static/app.js` | Resilient terminal task watching |

## Public interfaces

Added Console collections:

- `GET /api/v1/factory/sealed-datasets`
- `GET /api/v1/factory/leakage-reports`
- `GET /api/v1/factory/training-approvals`
- `GET /api/v1/factory/training-environments`
- `GET /api/v1/factory/training-jobs`
- `GET /api/v1/factory/training-terminals`
- `GET /api/v1/factory/training-admissions`

Added confirmed mutations for sealing, approval issue/revoke, environment probe,
and training start under `/api/v1/factory/`.

Added service CLI options:

- `--training-environment-directory`
- `--training-wheelhouse-manifest`
- `--training-model-directory`

All three are required together; omitting all keeps real training disabled.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check .
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.contract.test_schema_roundtrip -v
MYPYPATH=src PYTHONPATH=src:. .verification-venv/bin/mypy --strict \
  tools/phase22_training_exit tools/run_phase22_training_smoke.py
```

Result: 1,098 tests passed with three declared skips; Ruff passed; all 267
schemas and five schema-roundtrip tests passed; the strict physical-smoke tool
targets passed Mypy.

Physical result:

- status: `training.completed`
- environment: `e3d0a5a7d1a660e50fa5bf208bde92fbd038a260996ca3f865979c05cdc085b0`
- adapter: `3eb4fd1bcff497aea8cc49b9f868ab413c0dd284b0cfc4d16c3940fee47ada79`
- adapter bytes: `28,918,060`
- peak RAM / VRAM: `1,869,381,632` / `5,475,663,872`
- maximum temperature / measured energy: `45 °C` / `664 J`
- network denied, held-out absent, base frozen, unexpected trainables: true,
  true, true, none

## Evidence and artifacts

- Passing evidence: `artifacts/training/phase22-physical-smoke-20260717-05/evidence.json`
- Passing adapter: `artifacts/training/phase22-physical-smoke-20260717-05/jobs/phase22-physical-smoke-job/output/adapter/`
- Failed closed evidence: `artifacts/training/phase22-physical-smoke-20260717-01/` through `-04/`
- Wheel manifest: `artifacts/training/environment/wheelhouse-manifest.json`
- Model manifest: `artifacts/training/models/qwen3-1.7b-files.json`
- Architecture: `docs/architecture/PHASE22_REAL_EXPERT_FACTORY.md`
- Decision: `docs/decisions/0139-training-content-requires-explicit-authority-and-split-before-synthesis.md`

## Known limitations and risks

- `ProductFactoryTraining.start` is synchronous; a production Console scheduler
  must return durable admission/job state without holding one HTTP request.
- Service-stop reconciliation for an active worker still needs explicit terminal
  evidence rather than relying on process-parent death.
- The smoke has one training example and proves machinery only, not usefulness.
- Evaluation must receive held-out material through a separate authority and
  must never expose it to the training workspace.
- The source service can expose training only when exact external artifacts are
  configured; release assembly does not package/provision them yet.

## Operational notes

The 4.08 GB Qwen model and offline environment remain under
`artifacts/training/`. No training scope remains active. Ollama models were
unloaded before each admitted smoke because the resource policy correctly denies
concurrent inference. Failed and passing artifact directories are retained as
append-only evidence.

## Recommended next entry point

Implement Phase 22.6 before any conversion or activation. Read
`docs/architecture/PHASE22_REAL_EXPERT_FACTORY.md`, this handoff,
`src/fam_os/expert_factory/training_backend.py`, and
`src/fam_os/product/factory_training.py`. First add immutable held-out evaluation
authority, suite/measurement/comparison contracts, encrypted append-only
persistence, and a separate network-denied evaluator that compares the candidate
adapter and incumbent under identical quality, safety, latency, RAM, VRAM,
energy, size, and scheduler gates. The smoke adapter must remain non-promotable.
