# Handoff 0190: Engineering authority integration surfaces

**Date:** 2026-07-18  
**Plan step:** Phase 24.5  
**Status:** Complete for step 24.5; Phase 24 remains in progress  
**Previous handoff:** `0189-strict-engineering-results-and-receipts.md`

## Objective

Expose every new engineering authority consistently at deterministic ingress,
signed expert routing, schemas, Console/Shell presentation, and truthful
integration coverage without making any new effect production-reachable.

## Scope completed

- Added deterministic recognition patterns for all fourteen engineering
  authorities and attached requirements to action-intent decisions.
- Preserved fail-closed behavior: recognizing a high-risk request does not
  resolve a capability or create a grant.
- Extended signed code-expert scopes with `advisory_authorities` and configured
  the packaged Qwen, Gemma, and Laguna code scopes for the full vocabulary.
- Rejected engineering advisory claims from experts lacking signed `code.*`
  capability.
- Added model-free Shell engineering result rendering and Console labels for
  each Phase 24.4 proposal/receipt/unavailable discriminator.
- Added one explicit component-only integration coverage item for every
  authority.

## Explicitly not completed

- Advisory expert scopes are not owner grants and cannot dispatch an effect.
- No new provider or capability is production-reachable.
- Delegation modes, live grant/revocation policy, break-glass approval,
  assurance waiver labels, and the Phase 24 exit proof remain open.
- No signed release was built or installed for this source-level change.

## Architecture and decisions

ADR 0166 separates signed permission to generate advice from owner authority to
cause effects. Deterministic recognition runs before model selection and only
reports requirements. Result projection consumes Core-owned discriminators and
does not render model proposal summaries as trusted receipts.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/production/action_intent.py` | Recognizes all authority requirements without granting them. |
| `src/fam_os/core/production/model_catalog_scopes.py` | Validates signed advisory authority scopes. |
| `src/fam_os/core/production/model_catalog.py` | Retains signed advisory provenance. |
| `configs/packages/runtime/model-catalog.json` | Declares advisory coverage for packaged code experts. |
| `src/fam_os/product/resources/runtime/model-catalog.json` | Keeps the installed resource copy exact. |
| `src/fam_os/shell/engineering_projection.py` | Renders strict engineering truth states. |
| `src/fam_os/shell/__init__.py` | Exports the engineering renderer. |
| `src/fam_os/console/static/task_updates.js` | Labels engineering proposals and receipts. |
| `configs/integration/coverage.json` | Tracks all fourteen authorities as component-only. |
| `tests/unit/test_action_intent_firewall.py` | Covers every recognized authority. |
| `tests/unit/test_packaged_runtime_catalog.py` | Covers signed advisory-scope validation. |
| `tests/unit/test_shell_engineering_projection.py` | Covers model-free Shell projection. |
| `tests/unit/test_console_task_updates.py` | Covers Console result labels. |
| `tests/contract/test_integration_coverage.py` | Prevents maturity overstatement or missing authorities. |
| `docs/decisions/0166-expert-engineering-scopes-are-advisory-only.md` | Records the advice/effect separation. |
| `MASTER_PLANv2.md` | Records Phase 24.5 evidence. |

## Public interfaces

- `recognize_engineering_authorities(prompt)`
- `ActionIntentDecision.required_engineering_authorities`
- `RuntimeExpertScope.advisory_authorities`
- `RuntimeModelProvenance.advisory_authorities`
- `render_engineering_result(value)`
- Console presentation labels for all five engineering result kinds.
- Coverage IDs `engineering_authority.<authority>` for every authority.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_engineering_contracts \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility \
  tests.contract.test_cross_contract_references \
  tests.unit.test_action_intent_firewall \
  tests.unit.test_packaged_runtime_catalog \
  tests.unit.test_shell_engineering_projection \
  tests.unit.test_console_task_updates \
  tests.contract.test_integration_coverage
```

Result: 78 tests passed.

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
git diff --check -- <Phase 24 source, configuration, tests, and documentation>
```

Result: all 302 generated schemas validated and the whitespace check passed.

The full-suite host dependency limitation remains exactly as recorded in
Handoff 0188; no dependency was installed or changed.

## Evidence and artifacts

- `docs/decisions/0166-expert-engineering-scopes-are-advisory-only.md`
- `configs/integration/coverage.json`
- `tests/unit/test_action_intent_firewall.py`
- `tests/unit/test_packaged_runtime_catalog.py`

## Known limitations and risks

- Recognition is deterministic phrase classification, not semantic proof of
  task completeness; admission must still compare an exact task envelope.
- Advisory scope is retained in signed catalog provenance but is not yet used
  to select a production engineering planner.
- Console labels are ready for strict engineering results, but no production
  endpoint emits those results yet.

## Operational notes

No services, packages, models, credentials, external repositories, or
operating-system state were changed.

## Recommended next entry point

Continue with Phase 24.6 and 24.7. Read ADRs 0165–0166 and add versioned,
owner-visible delegation profiles plus target/time/purpose-bound revocable grant
contracts. Keep profile expansion deterministic and never persist a hidden
master boolean.
