# Handoff 0145: Production grounded answers

**Date:** 2026-07-17  
**Plan step:** Phase 20.3  
**Status:** Complete  
**Previous handoff:** `0144-production-expiring-document-indexing.md`

## Objective

Make installed FAM_OS identity and project answers consume only authorized local
sources, release only claim-complete verified output, and expose exact citations
through Shell, Console, and MCP.

## Scope completed

- Added a typed Core grounding port and production request preparer for identity,
  project, repository, citation, and retrieval intents.
- Added a signed packaged FAM_OS identity document that states the real product
  boundary rather than allowing model invention.
- Connected active encrypted document indexes to production generation with
  owner, purpose, application, session, workspace, and expiry checks plus model,
  similarity, source-count, and character bounds.
- Added one shared strict retrieval candidate parser. Released answer bytes must
  exactly equal the ordered claim texts, and every claim carries an exact quote
  from one declared source.
- Reused the signed declared retrieval verifier and refreshed every source
  verifier manifest/binding to the new canonical verifier tree digest.
- Added terminal projection from verified internal JSON to natural answer text
  and typed digest-bound exact citations.
- Propagated citations through Core, Shell, Console, and MCP result contracts;
  added Shell and Console citation presentation.
- Added a safe stable Shell/Console no-source path with no inference fallback.
- Registered the result-citation schema and explicitly tracked the two strict
  hand-authored product configuration schemas, closing the prior renderer gap.
- Added unit, contract, transport, Console, production gateway, scope-isolation,
  restart, and fresh signed installed qualification coverage.

## Explicitly not completed

- Phase 20.4 inspect/correct/export/expire/delete surfaces and durable receipts.
- Phase 20.5-20.7 verified-outcome learning, live scheduler adaptation, and
  disable/reset/drift/rollback controls.
- Phases 21-23.

## Architecture and decisions

ADR 0127 makes grounding a Core policy decision, not a prompt convention. The
signed package resource is authoritative for product identity; persistent
project knowledge remains opt-in. Retrieved bytes are untrusted model context.
The same parser drives verification and presentation so uncited prose cannot be
introduced after verification. Missing or unauthorized sources fail closed.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/production/grounding_port.py` | Typed grounding boundary and request preparation. |
| `src/fam_os/product/grounded_retrieval.py` | Packaged identity and approved-index source selection. |
| `src/fam_os/verification/retrieval_candidate.py` | Shared strict claim-complete candidate parser. |
| `src/fam_os/core/production/grounded_result.py` | Verified answer and citation presentation. |
| `src/fam_os/core/contracts/result.py` | Typed exact result citations. |
| `src/fam_os/product/resources/FAM_OS_IDENTITY.md` | Signed product identity source. |
| `src/fam_os/shell/render.py` | Safe terminal citation presentation. |
| `src/fam_os/console/static/` | Console exact-citation presentation. |
| `tools/phase20_grounding_exit/` | Installed qualification components. |
| `artifacts/memory/phase20.3-grounded-answers.json` | Passing signed evidence. |

## Public interfaces

- `ResultCitation` on `TaskResult` and `ShellResult`
- Schema `fam.core.result-citation/v1alpha1`
- Shell `Exact citations` result section
- Console `Exact citations` result section
- Safe Shell error code `shell.grounding_unavailable`
- `tools/run_phase20_grounding_exit.py`

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check src tests tools connectors/vscode/test
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -t .
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/contract -t .
MYPYPATH=src:tools .verification-venv/bin/mypy --explicit-package-bases <21 affected targets>
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:tools .verification-venv/bin/python tools/run_phase20_grounding_exit.py
git diff --check
```

Results: 961 tests pass with two declared skips; 39 architecture tests, 35
contract tests, 21 affected Mypy targets, whole-tree Ruff, 192 schema artifacts,
and diff checks pass. A fresh Ed25519-signed seven-component installation reports
`passed: true` for packaged identity, no-source denial, approved project
retrieval, cross-application source isolation, exact citations, signed verifier
evidence, active-index restart persistence, healthy diagnosis, and complete
removal.

## Evidence and artifacts

- `artifacts/memory/phase20.3-grounded-answers.json`
- `tests/unit/test_product_grounded_retrieval.py`
- `tests/unit/test_retrieval_candidate.py`
- `tests/unit/test_production_task_gateway.py`
- `tests/integration/test_console_http.py`
- `docs/decisions/0127-grounded-answers-require-authorized-sources-and-exact-claims.md`
- `docs/operations/PHASE20_GROUNDED_ANSWERS.md`

## Known limitations and risks

- Retrieval is lexical-intent-triggered and embedding-ranked; Phase 23 still owns
  real-model CPU-only and full-workstation quality matrices.
- Current Shell and MCP calls do not carry a trusted workspace identity, so a
  workspace-only grant fails closed unless another allowed scope applies.
- The model can choose poor wording while remaining fully cited; deterministic
  citation verification proves source binding, not general answer quality.
- The signing key is ephemeral qualification evidence, not a production trust
  anchor.

## Operational notes

Verifier Python changes require refreshing every verifier manifest and binding
artifact digest before activation can pass. The installed qualification creates
only temporary signed roots and removes them after diagnosis.

## Recommended next entry point

Begin Phase 20.4 from `src/fam_os/product/document_index_service.py`,
`src/fam_os/memory/management.py`, and the Console Memory surface. Define typed
inspect, correction, export, manual-expiry, and deletion requests plus durable
receipts before adding mutations.
