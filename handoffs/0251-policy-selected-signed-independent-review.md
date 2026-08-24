# Handoff 0251: Policy-selected signed independent review

**Date:** 2026-07-19  
**Plan step:** Phase 30.8, 30.5, and 30.9  
**Status:** Partial  
**Previous handoff:** `0250-automatic-governed-documentation-regeneration.md`

## Objective

Replace the ambiguous component review gate with a policy-selected,
release-signed, independently produced, evidence-resolved, owner-visible review
checkpoint in the active natural engineering lifecycle.

## Scope completed

- Added immutable review selections binding task, candidate, complete changeset
  digest, admitted-intent digest, policy, and required disciplines.
- Added deterministic code/security/architecture/design selection; every
  mutation selects code review and risk-sensitive tasks add the applicable
  disciplines.
- Added Ed25519 release-signed reviewer recipes, secure installed-recipe
  loading, release assembly, and a bounded deterministic reviewer with no
  effect authority.
- Composed selection and signed review after final candidate verification and
  before the owner changeset checkpoint. Missing, mismatched, or blocked review
  denies apply.
- Replaced arbitrary resolution strings with typed receipts bound to exact
  remediation edits and passing verification evidence already stored by Core.
- Persisted selections, resolution receipts, and waiver decisions in the
  owner-encrypted restart-safe review store.
- Added an explicit session-authenticated Console and Shell waiver ceremony
  showing exact consequences and truthful reduced assurance.
- Exposed review checkpoints and immutable supporting evidence through natural
  progress, authenticated Console, and typed Shell state.
- Added real repository integrations proving a signed passing code review and a
  signed blocking security finding followed by exact owner waiver, apply,
  reverification, and local commit.

## Explicitly not completed

- A new signed installed candidate or live production-verifier run containing
  these changes.
- The independent human security review required by Phase 31.5.
- Semantic model-assisted or human review beyond the bounded release-owned
  deterministic reviewer.
- Remaining Phase 27/29 powers, complete Phase 30.9 composition, final profile
  matrices, 24-hour soak, and final direct-evidence coverage promotion.

## Architecture and decisions

ADR 0216 makes a durable policy selection and release-signed independent
checkpoint mandatory in the composed review path. Review evidence is distinct
from mutable checkpoint revisions. Resolution is a trusted evidence lookup;
waiver is an explicit owner decision with reduced assurance, not a forged pass.

The deterministic reviewer is independently identified from the generating
model and has no effect authority. This satisfies the installed runtime
reviewer boundary when qualified, but it is deliberately not represented as
the later independent human review.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/review.py` | Add selection, signed recipe, and typed resolution contracts. |
| `src/fam_os/core/engineering/review_policy.py` | Select required disciplines deterministically. |
| `src/fam_os/core/engineering/review_recipes.py` | Verify signed recipes and bind reviewer output. |
| `src/fam_os/adapters/review/deterministic.py` | Perform bounded exact-preview review. |
| `src/fam_os/adapters/sqlite/engineering_review.py` | Persist immutable review evidence beside checkpoint revisions. |
| `src/fam_os/product/engineering_review_api.py` | Recompute policy, validate typed evidence, and enforce passage. |
| `src/fam_os/product/natural_engineering_review.py` | Compose selection and signed review in the natural path. |
| `src/fam_os/product/natural_engineering_review_governance.py` | Run the owner-authenticated waiver ceremony. |
| `src/fam_os/product/service.py` | Load and compose the installed signed reviewer. |
| `src/fam_os/console/static/natural_engineering.js` | Present blocking findings and exact waiver action. |
| `src/fam_os/adapters/shell/natural_engineering.py` | Present the same typed Shell approval. |
| `tests/integration/test_natural_engineering_review.py` | Prove block, waiver, apply, reverify, and commit. |

## Public interfaces

- `EngineeringReviewSelection`
- `SignedEngineeringReviewerRecipe`
- `EngineeringReviewResolutionReceipt`
- `EngineeringReviewExecutionService`
- `ProductEngineeringLoopApi.record_review_selection(...)`
- `ProductEngineeringLoopApi.record_trusted_review_resolution(...)`
- `ProductEngineeringLoopApi.waive_review_finding(...)`
- `POST /api/v1/engineering/natural-language/proposals/{id}/review-waiver`
- Console review responses now include immutable `evidence`.
- `ShellEngineeringLoopResponse.review_evidence`

The old `EngineeringReviewService.resolve(checkpoint_id, finding_id,
receipt_id, ...)` interface is removed; resolution now accepts only
`EngineeringReviewResolutionReceipt`.

## Validation

```bash
node --check src/fam_os/console/static/natural_engineering.js
env PYTHONPATH=src:. python3 tools/render_contract_schemas.py
env PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_review_execution \
  tests.unit.test_engineering_review_service \
  tests.unit.test_product_engineering_review_api \
  tests.unit.test_product_natural_engineering_api \
  tests.unit.test_fam_shell_natural_engineering \
  tests.unit.test_fam_shell_engineering_loop_transport \
  tests.unit.test_installed_integration_recipes \
  tests.unit.test_release_bundle \
  tests.integration.test_console_natural_engineering \
  tests.integration.test_console_engineering_loop \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_natural_engineering_review \
  tests.integration.test_natural_engineering_incident \
  tests.integration.test_natural_engineering_publication \
  tests.integration.test_product_service \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references
env PYTHONPATH=src:. python3 -m unittest discover -s tests/architecture -t .
git diff --check
```

Result: 76 affected tests passed, 41 architecture tests passed, all 413 schemas
rendered, JavaScript syntax and `git diff --check` passed. No live service was
changed.

## Evidence and artifacts

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T10-52-05-951Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T10-55-29-934Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T10-55-30-882Z.log`
- `docs/decisions/0216-policy-selected-review-requires-signed-independent-evidence.md`

## Known limitations and risks

- The active signed release predates these changes; installed production
  composition remains unproved until a new candidate is built and installed.
- The deterministic reviewer catches bounded structural risks and proves the
  independent checkpoint boundary; it is not a substitute for human semantic
  judgment or the Phase 31.5 external review.
- A typed resolution path is present and tested at the trusted product boundary;
  the natural loop currently exercises pass and explicit waiver, not automated
  post-review candidate remediation.
- The required host AppArmor profile remains an external owner-administration
  gate for production sandbox qualification.

## Operational notes

No running service, active release, model, owner repository, remote, credential,
or host security policy was changed. Integration repositories were temporary.

## Recommended next entry point

Build a new signed integrated candidate containing Handoffs 0247–0251, run the
installed package review pass/block/waiver paths, and obtain owner authorization
to load `fam-os-userns` before live production-verifier qualification. Then
continue the remaining Phase 27 authority powers through the same natural
lifecycle.
