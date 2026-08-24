# Handoff 0143: Production ephemeral session memory

**Date:** 2026-07-17  
**Plan step:** Phase 20.1  
**Status:** Complete  
**Previous handoff:** `0142-production-declared-verifier-bindings.md`

## Objective

Turn the existing bounded Phase 10 ephemeral store into default production
conversation memory without persisting it, leaking it across sessions, or
allowing remembered text to acquire authority.

## Scope completed

- Added a thread-safe production session-memory service over the existing
  digest-verifying, exact-scope ephemeral store.
- Enforced rolling record, total-byte, per-turn, context-record, context-byte,
  and eight-hour TTL bounds with oldest-record capacity eviction.
- Added one stable memory-session ID per terminal Shell controller lifetime.
- Bound Console memory to the server-issued HttpOnly session and ignored
  client-selected memory IDs.
- Reused authenticated MCP principal/session scope through `ask_as`.
- Recorded prompts only after admission and assistant content only after safe
  final-result release.
- Injected prior exact-session turns into inference as explicitly untrusted and
  nonauthoritative conversation while leaving the durable request prompt intact.
- Cleared the process-only memory on service stop/restart.
- Added focused unit, transport, composed product, cross-session, and signed
  installed restart/removal evidence.

## Explicitly not completed

- Phase 20.2 opt-in document/folder indexing and expiry.
- Phase 20.3 exact local citation grounding, Phase 20.4 management surfaces,
  or Phase 20.5-20.7 verified learning and drift controls.
- Phases 21-23.

## Architecture and decisions

ADR 0125 separates the default volatile conversation window from all persistent
memory. Trusted ingress owns the scope. Remembered text is appended only to the
user inference message beneath a nonauthority warning; it cannot modify the
already admitted capabilities, immutable plan, approval, verifier declaration,
or assurance policy.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/memory/session_memory.py` | Bounded process-only session memory. |
| `src/fam_os/core/production/memory_port.py` | Core dependency-inversion port. |
| `src/fam_os/core/production/execution_worker.py` | Exact-session context injection. |
| `src/fam_os/core/production/gateway.py` | Admission and final-release capture. |
| `src/fam_os/shell/contracts.py` | Bounded Shell memory-session identity. |
| `src/fam_os/console/tasks.py` | Trusted Console-session binding. |
| `tools/phase20_memory_exit/` | Small installed qualification components. |
| `artifacts/memory/phase20.1-session-memory.json` | Passing signed evidence. |

## Validation

```bash
.verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check .
.verification-venv/bin/python -m unittest discover -s tests/architecture -t .
MYPYPATH=src .verification-venv/bin/mypy --explicit-package-bases <affected modules>
.verification-venv/bin/python tools/run_phase20_memory_exit.py
```

Results: 935 Python tests pass with two declared skips; 39 architecture tests,
Ruff, and the affected Mypy profiles pass. The fresh signed installed report has
`passed: true`, exact same-session inclusion, cross-session and restart
exclusion, no plaintext nonce in the durable database, healthy diagnosis, and
complete removal.

## Evidence and artifacts

- `artifacts/memory/phase20.1-session-memory.json`
- `tests/unit/test_production_session_memory.py`
- `tests/integration/test_product_service.py`
- `docs/decisions/0125-session-memory-is-bounded-volatile-and-nonauthoritative.md`
- `docs/operations/PHASE20_SESSION_MEMORY.md`

## Known limitations and risks

- The qualification runtime is deterministic and inspects the exact installed
  model prompt; Phase 23 owns final real-model hardware matrices.
- Memory intentionally disappears on restart. Persistent continuity must not be
  added without the Phase 20.2 opt-in grant and management boundaries.
- The signing key is ephemeral qualification evidence, not a production trust
  anchor.

## Recommended next entry point

Begin Phase 20.2 by composing the existing `ApprovedDocumentIndex`, encrypted
document repository, and relevance policy behind an explicit owner-approved
folder/document grant with expiry. Do not scan a home directory or make
persistent memory implicit.

