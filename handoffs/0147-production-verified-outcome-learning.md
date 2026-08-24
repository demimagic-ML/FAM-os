# Handoff 0147: Production verified-outcome learning

**Date:** 2026-07-17  
**Plan step:** Phase 20.5  
**Status:** Complete  
**Previous handoff:** `0146-production-memory-management-controls.md`

## Objective

Connect installed verified terminal outcomes to a privacy-minimized local
learning record while removing terminal prompt and verifier working copies
without losing restart-safe results.

## Scope completed

- Added a strict content-free verified-learning contract with closed workflow
  intents, model/tier metadata, power-of-two context buckets, escalation state,
  evidence binding, local-only policy, and explicit no-content invariants.
- Added migration 0013 with owner-encrypted terminal-result and verified-learning
  tables plus request-indexed candidate evidence.
- Added one atomic terminal transaction that retains the presented result,
  optionally inserts one verified learning observation, redacts request and
  application prompt copies, redacts every attempt candidate and verifier
  feedback, and removes the completed verification declaration.
- Required verified inference assurance, verified result status and assurance,
  release disposition, and a passing acceptance-to-candidate binding. Unverified
  terminal work is normalized and retained for the user but never learned.
- Preserved exact citations, verifier status/facts/provenance, action results,
  deterministic undo, and repeated/restart result reads.
- Made terminal normalization background-complete even without continued client
  polling and idempotent under concurrent result projections.
- Composed the producer into the installed Shell, Console, MCP, inference, and
  application task lifecycle through one Core terminal-outcome port.
- Added contract, transaction rollback, concurrency, escalation/repair,
  application-action, restart, production-service, and fresh signed installed
  qualification coverage.

## Explicitly not completed

- Phase 20.6 live frequency, context, escalation, and prefetch consumers.
- Phase 20.7 visible inspection, disable, reset, drift, and rollback controls.
- Phases 21-23.

## Architecture and decisions

ADR 0129 makes final result retention the prerequisite for terminal content
normalization. Learning is not a copy of conversation or evidence: it is a
minimal encrypted feature record whose constructor forbids retained prompt,
candidate, source, and application payload fields. Terminal results carry no
learning authority. Existing Phase 11 predictors remain disconnected until
Phase 20.6 applies bounded production policy.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adaptation/verified_learning.py` | Strict privacy-minimized learning contract. |
| `src/fam_os/product/verified_outcome_learning.py` | Verified terminal eligibility and feature derivation. |
| `src/fam_os/product/storage/terminal_outcome_repository.py` | Atomic terminal retention, learning, and redaction. |
| `src/fam_os/product/storage/terminal_redaction.py` | Typed nested content normalization. |
| `src/fam_os/product/storage/migrations/0013_verified_terminal_outcomes.sql` | Durable result and learning schema. |
| `src/fam_os/core/production/terminal_projection.py` | Stored-result projection and terminal outcome port. |
| `src/fam_os/core/production/gateway.py` | Background and concurrent-safe finalization. |
| `tools/phase20_learning_exit/` | Installed qualification processes. |
| `artifacts/adaptation/phase20.5-verified-learning.json` | Passing signed evidence. |

## Public interfaces

- Contract `fam.adaptation.verified-learning/v1alpha1`
- `ProductVerifiedOutcomeLearning.records()`
- Core `TerminalOutcomePort`
- `tools/run_phase20_learning_exit.py`

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -t .
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/contract -t .
.verification-venv/bin/ruff check src tests tools connectors/vscode/test
MYPYPATH=src:tools .verification-venv/bin/mypy --explicit-package-bases <17 affected targets>
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:tools .verification-venv/bin/python tools/run_phase20_learning_exit.py
git diff --check
```

Results: 982 tests pass with two declared skips; 39 architecture tests, 35
contract tests, 17 affected Mypy targets, whole-tree Ruff, 200 schema artifacts,
and diff checks pass. A fresh Ed25519-signed seven-component installation reports
`passed: true` for verified-only learning, unverified exclusion, terminal prompt
and working-evidence normalization, encrypted-at-rest nonce absence, result and
learning restart persistence without inference replay, healthy diagnosis, and
complete removal.

## Evidence and artifacts

- `artifacts/adaptation/phase20.5-verified-learning.json`
- `tests/unit/test_verified_outcome_learning.py`
- `tests/unit/test_production_task_gateway.py`
- `tests/integration/test_product_application_action.py`
- `tests/integration/test_product_service.py`
- `docs/decisions/0129-terminal-outcomes-are-normalized-before-local-learning.md`
- `docs/operations/PHASE20_VERIFIED_LEARNING.md`

## Known limitations and risks

- The installed producer records safe features but does not yet change scheduling;
  Phase 20.6 owns those consumers and measured benefit.
- Context tokens use a conservative character-derived bucket, not a provider
  tokenizer. Live policy must treat it as a lower-fidelity planning feature.
- Terminal verifier feedback is normalized, reducing post-hoc debugging detail;
  stable status, facts, digests, package trust, and final result remain.
- Phase 20.7 still owns visible record inspection and reset.
- The qualification signing key is ephemeral evidence, not a production trust
  anchor.

## Operational notes

Do not add prompt hashes, embeddings, candidate snippets, source excerpts, or
application parameters to the learning contract. New features require an ADR,
privacy bounds, a schema revision, and installed nonce-absence evidence.

## Recommended next entry point

Begin Phase 20.6 from `ProductVerifiedOutcomeLearning.records()`,
`LocalExpertFrequencyLearner`, `LocalOutcomePredictor`, and
`DeterministicTransitionPredictor`. Define one bounded production prediction
snapshot before allowing any scheduler prewarm or context-budget effect.
