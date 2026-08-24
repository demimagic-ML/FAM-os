# Handoff 0142: Production declared verifier bindings

**Date:** 2026-07-17  
**Plan step:** Phase 18.6 and Phase 18 exit  
**Status:** Complete  
**Previous handoff:** `0141-phase19-signed-application-weaving-exit.md`

## Objective

Close the final Phase 18 gap by making exact-text, Python, retrieval,
mathematics, and media verification selectable and executable through the
installed production Core with exact signed evidence and no model-owned verdict.

## Scope completed

- Added versioned typed verification declarations, media reports, run records,
  schemas, Shell wire input, and Console document parsing.
- Persisted declarations and every verifier attempt in encrypted migrated
  product storage.
- Compiled declaration acceptance IDs into immutable plans and bound released
  evidence to the admitted request and exact candidate.
- Added an explicit production verifier catalog with canonical implementation
  digests, fixed entrypoint allowlists, signed-release trust evaluation, and
  fail-closed manifest/binding activation.
- Connected deterministic exact text, Bubblewrap Python tests, byte-bound
  retrieval citations, safe-AST SymPy equivalence, and media artifact/text
  adapters.
- Forwarded bounded image bytes through the inference port and Ollama payload.
- Preserved complete Python test source and sandbox diagnostics in bounded repair
  feedback, retaining both failed and passing run records.
- Added five production verifier manifests and five exact runtime bindings.
- Added signed installed qualification covering all five domains, diagnosis,
  and complete removal.

## Explicitly not completed

- Phase 20 memory, retrieval-index, and local-adaptation production composition.
- Phase 21 physical trusted peers, Phase 22 real LoRA/QLoRA Expert Factory, or
  Phase 23 final matrices, soak, and independent security review.

## Architecture and decisions

ADR 0124 keeps verification declarative and owned by Core. Shell transports a
bounded canonical declaration document and gains no privileged verifier import.
Only explicit package/adapter pairs may activate. The exact installed verifier
tree is hashed, while the verified release signature supplies signed effective
trust. Candidate text can propose an answer but cannot select, weaken, or pass
its acceptance contract.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/verification/declarations.py` | Typed declarations and durable run evidence. |
| `src/fam_os/verification/domain_adapters.py` | Five deterministic production adapters. |
| `src/fam_os/verification/activation.py` | Exact catalog and binding activation. |
| `src/fam_os/core/production/declared_verifiers.py` | Production invocation and persistence. |
| `src/fam_os/product/composition/verifier_unit.py` | Source/signed release catalog composition. |
| `src/fam_os/product/storage/verification_repository.py` | Encrypted declarations and runs. |
| `configs/packages/verifiers/` | Production verifier manifests. |
| `configs/packages/verifier-bindings/` | Exact runtime bindings. |
| `tools/phase18_verifier_exit/` | Small installed qualification components. |
| `artifacts/verification/phase18-production-verifiers.json` | Passing signed installed evidence. |

## Public interfaces

- Shell wire command `verified_ask`
- Console task request field `verification`
- `GET /api/v1/tasks/{task_id}/verification`
- Contracts `fam.verifier.declaration/v1alpha1`,
  `fam.verifier.run/v1alpha1`, and `fam.verifier.media-report/v1alpha1`
- `tools/run_phase18_verifier_exit.py`

## Validation

```bash
.verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check .
MYPYPATH=src:tools .verification-venv/bin/mypy --explicit-package-bases <affected Phase 18 modules>
.verification-venv/bin/python tools/run_phase18_verifier_exit.py
```

Results: 929 Python tests pass with two declared skips; Ruff, the affected source
Mypy profile, and architecture boundaries pass. The newly built signed installed
report has `passed: true`, five verified task domains, exact signed verifier
bindings, one forwarded media image, healthy diagnosis, and complete removal.

## Evidence and artifacts

- `artifacts/verification/phase18-production-verifiers.json`
- `tests/integration/test_production_verifier_bindings.py`
- `docs/decisions/0124-typed-signed-production-verifier-bindings.md`
- `docs/operations/PHASE18_PRODUCTION_VERIFIERS.md`

## Known limitations and risks

- The qualification key is ephemeral test evidence, not a production trust
  anchor.
- This run proves one Linux installation. Phase 23 owns independent hardware
  matrices and the final long-running qualification.
- Whole-tree strict Mypy retains pre-existing findings outside the affected
  profile; no broader clean-Mypy claim is made.

## Recommended next entry point

Begin Phase 20.1. Compose bounded ephemeral session memory into the same durable
Core lifecycle without making persistent memory implicit. Read the existing
Phase 10 memory contracts and handoff 0093 before selecting the production
storage and Console/Shell surfaces.

