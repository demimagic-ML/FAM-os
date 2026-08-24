# Handoff 0154: Production complete remote evidence

**Date:** 2026-07-17  
**Plan step:** Phase 21.5  
**Status:** Complete  
**Previous handoff:** `0153-production-remote-core-route.md`

## Objective

Bind every releasable remote candidate to one durable, content-free record of the
complete authenticated exchange, and prove an actual partial mutual-TLS response
cannot become candidate evidence or durable content.

## Scope completed

- Added strict `RemoteExecutionEvidence`, disposition, and verification-outcome
  contracts with exact identity, digest, byte-count, time, and finalization
  invariants.
- Added the 239th generated public schema and round-trip fixture.
- Made the remote client return the authenticated request, result, and exact
  context evidence only after full frame, receipt, signature, identity, and
  digest validation.
- Atomically inserted the complete candidate and encrypted pending remote record.
- Atomically finalized verified acceptance and released remote evidence; retained
  content-free rejected or withheld outcomes under their exact policy state.
- Required final-result policy to resolve and validate the remote evidence
  referenced by the terminal plan transition before release.
- Added the authenticated Console
  `GET /api/v1/tasks/{task}/remote-execution` audit endpoint.
- Covered verified release, rejected remote/local repair, unavailable policy,
  forged or unfinished evidence, and truncated-output non-retention in source
  tests.
- Added small installed-exit tools for complete evidence inspection and one
  controlled authenticated partial-frame server; no production backdoor or
  alternate execution lifecycle was introduced.

## Installed exit evidence

A fresh Ed25519-signed seven-component release was installed into two isolated
prefixes and paired through the real comparison ceremony. The desktop selected
downloaded `gemma4:26b`, transferred one approved context, received a complete
peer-signed result, passed the signed exact-text verifier, and released `READY`.
Console and installed-code database inspection returned the same finalized
content-free record, including request, plan, disclosure receipt, signed result,
budget, candidate, acceptance, and verifier identities. The terminal result
referenced that record. The ordinary local task had no remote record.

The normal peer service was then stopped and replaced at the paired endpoint by
a controlled installed-code mutual-TLS process. It authenticated the desktop,
read the complete 2,646-byte request frame, declared a 72-byte response, sent
only a 40-byte sentinel, and closed. Core produced a safe failed terminal result
with no content. It retained the durable remote budget reservation but created
no candidate, remote evidence, or additional context-disclosure receipt. Neither
SQLite database contained the sentinel. Both installations diagnosed healthy
and were completely removed.

## Explicitly not completed

- Phase 21.6 must reconcile the pending execution flag and durable reservation
  after disconnect or restart, classify uncertain completion, and retry locally
  only under unchanged acceptance and remaining budget.
- Phase 21.7 must repeat the final success/loss scenario between two physical
  Linux machines; this gate used two isolated installations on one workstation.
- Remote binary media remains denied pending an exact binary-context contract.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/fabric/remote_evidence.py` | Strict content-free evidence contract |
| `src/fam_os/core/production/remote_evidence.py` | Authenticated exchange to evidence builder |
| `src/fam_os/product/storage/final_evidence_repository.py` | Atomic encrypted persistence and finalization |
| `src/fam_os/core/production/execution_worker.py` | Complete-result candidate/evidence transaction |
| `src/fam_os/core/production/verification_flow.py` | Verification disposition and acceptance binding |
| `src/fam_os/core/lifecycle/final_service.py` | Terminal remote-evidence release policy |
| `src/fam_os/console/tasks.py` | Authenticated content-free task audit facade |
| `tools/phase21_evidence_exit/` | Complete and actual partial-frame qualification |

## Validation

```bash
PYTHONPATH=src:tools:. .verification-venv/bin/python tools/run_phase21_remote_evidence_exit.py
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check
.verification-venv/bin/ruff check src tests tools
.verification-venv/bin/mypy <15 affected source files>
MYPYPATH=../src:. ../.verification-venv/bin/mypy --ignore-missing-imports --explicit-package-bases <8 affected tools>
git diff --check
```

Result: the signed installed gate passed both complete and truncated-frame
scenarios with healthy diagnosis and complete removal. The full suite passes
1,047 tests with two declared skips; Ruff, affected Mypy, all 239 schemas,
contract tests, and diff validation pass.

## Evidence

- `artifacts/fabric/phase21.5-complete-remote-evidence.json`
- `schemas/v1alpha1/fam.fabric.remote-execution-evidence.schema.json`
- `tests/integration/test_product_remote_execution.py`
- `tests/unit/test_core_final_result_policy.py`
- `tests/integration/test_console_http.py`

## Next step

Phase 21.6 must recover from disconnect and restart without treating a started
remote attempt as free. It must reconcile the durable reservation and execution
record, discard all partial state, preserve the original acceptance contract,
and use a remaining local attempt only when every authority and policy input is
unchanged.
