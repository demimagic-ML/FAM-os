# Handoff 0132: Restart-safe action reconciliation

**Date:** 2026-07-17  
**Plan step:** Phase 17.4  
**Status:** Complete  
**Previous handoff:** `0131-durable-core-repositories-complete.md`

## Objective

Recover after daemon termination without repeating a mutation or silently
reusing approval.

## Scope completed

- Durable request recovery classifications for read, inference, and mutation.
- Safe-resume policy for read/inference only, without retained authority.
- Durable prepared/approved/invoking/uncertain/terminal action states.
- Fresh approval after restart for every pending mutation.
- Side-effect-free postcondition reconciliation for uncertain actions.
- Explicit invariant that restart decisions never authorize provider retry.
- Inconclusive reconciliation remains visible and retry-safe.

## Validation

```bash
PYTHONPATH=src:. python3.12 -m unittest discover -s tests
PYTHONPATH=src:. python3.12 tools/render_contract_schemas.py --check
```

Result: all 865 tests pass with seven declared environment skips; all 178
schemas render and the focused lint/typing gates pass.

## Known limitations and risks

- Expert, connector, and Ollama startup reconciliation remain coupled to their
  managed service implementation in Phase 17.5.
- The current narrow installed service has not yet been switched to secure
  storage; that composition occurs after managed runtime foundations exist.

## Recommended next entry point

Implement Phase 17.5: make FAM_OS supervise a dedicated owner Ollama service,
private model directory, health lifecycle, and shutdown. Reconcile actual Ollama
models with durable expert/runtime state without importing acceptance tooling.
