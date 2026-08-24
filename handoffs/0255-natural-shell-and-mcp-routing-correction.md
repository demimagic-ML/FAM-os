# Handoff 0255: Natural Shell and MCP routing correction

**Date:** 2026-07-19  
**Plan step:** Phase 30.5 regression correction  
**Status:** Partial  
**Previous handoff:** `0254-natural-sqlite-database-engineering.md`

## Objective

Restore exact coexistence between the natural engineering Shell path, explicit
Application Fabric capabilities, and delegated MCP ingress after the complete
source suite exposed routing regressions.

## Scope completed

- Prevented the implicit workspace natural-engineering handler from claiming a
  request that contains an explicit Application Fabric context.
- Preserved URI-only plain-language Shell routing to the master engineering
  loop.
- Required ambiguous “use” wording to name a concrete machine resource or path
  before the action firewall withholds it as a machine effect.
- Made delegated MCP execution return an immediate typed firewall terminal
  directly instead of looking it up as an asynchronous task.
- Added regressions for application-plus-workspace routing, conversational MCP
  interface wording, and terminal delegated refusal.
- Reproved the official MCP stdio bridge and the five previously failing legacy
  workspace/directory cases.

## Explicitly not completed

- A new signed installed candidate containing these corrections.
- The host AppArmor policy required by the production verifier.
- Any relaxation of action, application, MCP, or natural-engineering authority.

## Architecture and decisions

ADR 0220 assigns precedence to an explicit application context and treats an
immediate firewall terminal as a valid delegated outcome. ADR 0202 continues to
own the URI-only natural engineering checkpoints.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/shell/natural_engineering.py` | Explicit application-context routing precedence |
| `src/fam_os/core/production/action_intent.py` | Concrete-target requirement for ambiguous “use” wording |
| `src/fam_os/product/composition/mcp_ingress_executor.py` | Immediate terminal delegated result handling |
| `tests/unit/test_fam_shell_natural_engineering.py` | Application route regression |
| `tests/unit/test_action_intent_firewall.py` | Conversational interface regression |
| `tests/unit/test_mcp_ingress_executor.py` | Immediate terminal delegated-result regression |

## Public interfaces

No serialized contract or authority changed. Shell routing and MCP terminal
behavior are corrected within their existing public contracts.

## Validation

```bash
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_action_intent_firewall tests.unit.test_mcp_ingress_executor tests.integration.test_product_mcp_ingress -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_fam_shell_natural_engineering tests.integration.test_product_os_workflows tests.integration.test_verified_directory_action.VerifiedDirectoryActionTests.test_selected_workspace_resolves_named_child_without_model_inference -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests -q"
```

Result: the MCP/firewall suite passed 17 tests and the natural/legacy Shell
suite passed 14 tests. The complete source discovery executed 1,828 tests with
15 failures, 1 error, and 2 skips. All 15 failures are the existing production
verifier/remote/gateway group withheld behind the absent `fam-os-userns` host
profile. The one error is an intermittent legacy workspace-test
`shell.core_unavailable`; the exact case passed 20 consecutive isolated runs
and remains an order/timing investigation, not a claimed external gate.

Logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-31-21-544Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-31-21-538Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-31-36-956Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T12-34-13-602Z.log`

## Evidence and artifacts

- `docs/decisions/0220-natural-engineering-routing-does-not-override-explicit-application-authority.md`
- The validation logs above.

## Known limitations and risks

- The full source suite retains one low-frequency legacy Shell timing failure;
  the generic wire error hides its internal exception by design.
- Source passing tests are not installed release evidence.
- The production verifier failures must remain withheld until the owner loads
  the dedicated immutable AppArmor profile.

## Operational notes

No service, active release, repository, policy, package, port, credential, or
external system was changed.

## Recommended next entry point

Instrument the legacy Shell worker internally with content-safe failure
classification if the timing failure recurs, then continue Phase 27.13 natural
environment composition. Do not expose exception text on the wire.

