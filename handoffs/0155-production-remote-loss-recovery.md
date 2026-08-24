# Handoff 0155: Production remote loss recovery

**Date:** 2026-07-17  
**Plan step:** Phase 21.6  
**Status:** Complete  
**Previous handoff:** `0154-production-complete-remote-evidence.md`

## Objective

Reconcile a started remote attempt across disconnect and process restart, count
its budget exactly once, discard uncertain output, and retry locally only under
the unchanged acceptance and final-result contract.

## Scope completed

- Added exact failure classes and strict content-free
  `RemoteRecoveryEvidence` with one-way pending, recovered, failed, and denied
  dispositions.
- Bound the canonical request, active authority, plan, remote route, and verifier
  digest plus route-plan identity into durable remote and local-recovery budget
  reservations.
- Added `local_recovery` as an explicit shared-budget attempt kind.
- Persisted remote attempt consumption before networking, so restart never
  re-sends an uncertain request or treats it as free.
- Classified disconnect, timeout, partial result, uncertain completion, signed
  provider failure, authority change, authentication failure, and invalid result;
  only the first five may retry.
- Required unchanged acceptance, still-active authority, local model admission,
  and remaining token/time budget before one local retry.
- Added idempotent restart reconciliation for gaps after remote reservation,
  pending recovery, complete authenticated remote candidate, and complete
  recovered local candidate.
- Atomically finalized the recovered local candidate with its recovery evidence
  and required final-result policy to resolve the matching plan reference.
- Added authenticated Console recovery inspection at
  `GET /api/v1/tasks/{task}/remote-recovery`.
- Kept recovery orchestration in its own focused module; no alternate Core,
  peer, verifier, or release lifecycle was introduced.

## Installed exit evidence

A fresh Ed25519-signed seven-component release was installed into two isolated
prefixes and paired normally. The desktop probed the peer, confirmed the exact
privacy scope, and selected downloaded `gemma4:26b`. A controlled installed-code
mutual-TLS peer authenticated the desktop and received the complete 2,646-byte
request but sent zero response bytes. The desktop service was then killed with
`SIGKILL`; the peer observed requester loss.

Installed-code inspection after the crash found a running inference with one
bound 1,024-token/300-second remote reservation, the remote-attempt flag already
consumed, no candidate, no remote/recovery evidence, and no local reservation.
A fresh service process reopened the same encrypted state, recomputed the same
acceptance digest, selected local `qwen3:1.7b`, reserved exactly one
1,024-token/300-second `local_recovery` attempt, produced `READY`, passed the same
signed exact-text verifier, and released only with matching recovered evidence.
The total budget was 2,048 tokens and 600 seconds. No context receipt or prompt
was retained. Both installations diagnosed healthy and were completely removed.

## Explicitly not completed

- Phase 21.7 must repeat success and loss recovery across at least two physical
  Linux machines. Two prefixes, containers, VMs, or localhost are insufficient.
- Remote binary media remains denied pending an exact binary-context contract.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/fabric/remote_recovery.py` | Strict content-free recovery contract |
| `src/fam_os/core/production/remote_recovery.py` | Acceptance binding, classification, and reconciliation |
| `src/fam_os/core/production/execution_worker.py` | Pre-network consumption and local recovery route |
| `src/fam_os/core/lifecycle/global_budget.py` | Acceptance-bound attempt reservations |
| `src/fam_os/product/storage/final_evidence_repository.py` | Atomic encrypted recovery/candidate state |
| `src/fam_os/core/lifecycle/final_service.py` | Recovery-aware final release policy |
| `src/fam_os/console/tasks.py` | Owner-visible recovery audit facade |
| `tools/phase21_recovery_exit/` | Abrupt requester-loss installed qualification |

## Validation

```bash
PYTHONPATH=src:tools:. .verification-venv/bin/python tools/run_phase21_remote_recovery_exit.py
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check
.verification-venv/bin/ruff check src tests tools
.verification-venv/bin/mypy <19 affected source files>
MYPYPATH=../src:. ../.verification-venv/bin/mypy --ignore-missing-imports --explicit-package-bases <8 affected tools>
git diff --check
```

Result: the signed installed abrupt-loss/restart gate passed with signed local
verification, exact dual reservations, matching content-free recovery evidence,
healthy diagnosis, and complete removal. The full suite passes 1,053 tests with
two declared skips; Ruff, affected Mypy, all 240 schemas, contracts, and diff
validation pass.

## Evidence

- `artifacts/fabric/phase21.6-remote-loss-recovery.json`
- `schemas/v1alpha1/fam.fabric.remote-recovery-evidence.schema.json`
- `tests/integration/test_product_remote_execution.py`
- `tests/unit/test_remote_recovery.py`
- `tests/unit/test_core_final_result_policy.py`
- `tests/integration/test_console_http.py`

## Next step

Phase 21.7 must package this exact qualification for two real Linux hosts, record
their independently discovered hardware and device identities, run remote
success and network/requester-loss recovery over the physical network, inspect
both installed states, and remove both installations. Do not substitute
localhost, namespaces, containers, or virtual machines for physical evidence.
