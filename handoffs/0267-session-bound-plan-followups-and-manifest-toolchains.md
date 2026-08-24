# Handoff 0267: Session-bound plan follow-ups and manifest toolchains

**Date:** 2026-07-19
**Plan step:** Phase 30.1, 30.5, and 30.9 natural engineering composition
**Status:** Partial (`installed_tested`; real browser HTTP plan-to-implementation lifecycle passed)
**Previous handoff:** `0266-chatgpt-authenticated-codex-engineering-runtime.md`

## Objective

Fix the installed Console failure where `Implement the plan` lost the preceding
repository plan, selected an irrelevant file, and then rejected a Node
candidate because an unrelated Python utility caused a false Python verifier
requirement.

## Scope completed

- Added bounded owner/session/workspace plan references for explicit natural
  follow-ups.
- Kept current-message authority inference separate from referenced plan
  context; prior text cannot add high-risk powers.
- Made an unresolved plan reference fail before a grant with an actionable
  message instead of guessing a target.
- Exposed the complete deterministic architecture plan in the Console analysis
  result and retained it for same-session implementation.
- Passed the authenticated Console session into natural engineering and the
  Shell's stable memory session into the same product API.
- Made recognized repository manifests dominate verifier toolchain selection,
  with file-language inference used only for manifest-less repositories.
- Built and installed signed release
  `fam-os-natural-engineering-20260719-13`, activated
  `fam-os-natural-codex-13.service`, and verified authenticated Console session
  and snapshot HTTP 200 on port 8877.
- Ran one real two-turn browser HTTP lifecycle against a disposable Node
  repository containing an unrelated Python file. `Analyze ... and propose a
  plan` produced and retained the plan. `Ok, implement the plan` resolved it,
  selected only Node, generated six files, passed candidate verification,
  presented an exact changeset, applied only after approval, passed post-apply
  verification, and committed cleanly.
- Independently reran all three generated Node tests; all passed.

## Architecture and decisions

ADR 0231 binds plan references to the exact owner, authenticated transport
session, and canonical workspace. The resolved plan is task context only. The
current message remains the sole authority and high-risk input.

ADR 0232 makes recognized manifests authoritative for project toolchains. This
prevents arbitrary utility-file languages from imposing unrelated global test
suites while retaining manifest-less source-language fallback.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/natural_conversation.py` | Bounded plan reference and plan rendering |
| `src/fam_os/core/engineering/natural_language.py` | Separate current authority prompt from resolved task intent |
| `src/fam_os/core/engineering/__init__.py` | Export natural conversation contracts |
| `src/fam_os/product/natural_engineering_api.py` | Resolve/capture plans and select manifest-dominant toolchains |
| `src/fam_os/console/natural_engineering_routes.py` | Bind proposal creation to authenticated session |
| `src/fam_os/console/static/natural_engineering.js` | Display the plan and follow-up instruction |
| `src/fam_os/adapters/shell/natural_engineering.py` | Bind CLI follow-ups to stable Shell memory session |
| `src/fam_os/product/service.py` | Compose the bounded plan-reference service |
| `tests/unit/test_natural_engineering_conversation.py` | Session/workspace isolation tests |
| `tests/unit/test_natural_language_engineering.py` | Context-cannot-grant-authority regression |
| `tests/unit/test_product_natural_engineering_api.py` | Plan follow-up and toolchain regressions |
| `tests/integration/test_console_natural_engineering.py` | Console proposal/approval session binding |
| `tests/unit/test_fam_shell_natural_engineering.py` | Updated Shell product-port contract fixture |
| `docs/decisions/0231-*.md`, `0232-*.md` | Durable conversation and verifier policies |

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_natural_engineering_conversation \
  tests.unit.test_natural_language_engineering \
  tests.unit.test_product_natural_engineering_api \
  tests.integration.test_console_natural_engineering \
  tests.unit.test_fam_shell_natural_engineering

PYTHONPATH=src python3 -m unittest \
  tests.integration.test_natural_engineering_checkpoint \
  tests.integration.test_natural_engineering_incident \
  tests.integration.test_natural_runtime_diagnostics \
  tests.unit.test_product_service_startup_safety

PYTHONPATH=src python3 -m unittest discover -s tests/architecture
PYTHONPATH=src python3 -m compileall -q src tests
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Results:

- focused conversation/product/Console/Shell: 29 passed, 0 failed;
- the same 29 tests imported FAM_OS from signed release 13: 29 passed, 0 failed;
- lifecycle integration and service startup: 10 passed, 0 failed;
- architecture: 41 passed, 0 failed;
- compile, JavaScript parse, and diff checks: passed;
- full unit discovery: 1,586 ran with 8 pre-existing general
  answer-verifier/canary failures and 4 skips; the failures reproduce in their
  isolated modules and are outside natural engineering;
- installed real lifecycle: plan retained, follow-up resolved, Node-only
  verifier selected, one candidate and one post-apply verification receipt,
  clean commit `ed860c64bff46734f56f7981eb445150fe3810e2`;
- independent fixture test: 3 passed, 0 failed.

## Evidence

- `artifacts/product/phase30/natural-plan-followup-acceptance-20260719-01/evidence.json`
- release manifest SHA-256:
  `580760be8516522cd0a7e17f59ceda5581a27c81fce8f75c30e1bf23897f1b65`
- wheel SHA-256:
  `1ac95dd7b6c26bb29bd055343a0c47cfa2d9bee798444fa19ed2345c8784e328`
- Git receipt: `git-local-receipt-92b9f7205582440ea0dde5427a02fd85`

## Known limitations and risks

- Automatic plan-reference lookup is process-local. After a service restart,
  the owner must ask for the plan again or give a self-contained request even
  though durable task artifacts still exist.
- The deterministic repository plan is evidence-grounded but remains broad for
  vague prompts. A concrete requested outcome/path still produces better work.
- Node's installed generic test recipe can report success with zero discovered
  tests. This acceptance generated and ran three real tests, but zero-test
  sufficiency should receive a separate acceptance-policy decision.
- Phase 30 remains open for deliberate installed repair/escalation,
  separately approved publication, and the complete exit scenario matrix.

## Operational notes

- Active unit: `fam-os-natural-codex-13.service`.
- Browser Console: `http://127.0.0.1:8877` through the installed launcher.
- Shell socket: `/run/user/1000/fam-os-natural-codex-13/shell.sock`.
- State root: `/home/demimagic/.local/share/fam-os-natural-signed`.
- Release 12 remains installed and available for atomic rollback.

## Recommended next entry point

Persist the session/workspace plan-reference index by referencing existing
encrypted proposal/preparation records rather than duplicating plan content,
then separately define whether a zero-test run can satisfy candidate
acceptance. Continue the still-open Phase 30 installed repair/escalation and
publication scenarios after those policy decisions.
