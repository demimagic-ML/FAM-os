# Handoff 0253: Natural runtime diagnostic composition

**Date:** 2026-07-19  
**Plan step:** Phase 27.11 and installed portions of 30.1/30.5  
**Status:** Partial  
**Previous handoff:** `0252-owner-workspace-monitored-recovery-closure.md`

## Objective

Wire the existing signed runtime diagnostic toolchain into the installed
natural-language engineering lifecycle without granting clients recipe or
execution authority, and replace asserted performance baselines with an exact
pristine-candidate capture.

## Scope completed

- Added deterministic natural-intent selection for stack/crash, local trace,
  CPU/memory profile, race/leak, and exact-baseline performance work.
- Made natural selection fail closed when more than one admitted signed recipe
  claims the same diagnostic purpose, instead of choosing a version implicitly.
- Added task grant, principal, session, candidate/post-apply phase, and live
  authorization decision binding to diagnostic contracts.
- Added a Core service with pre-intent and immediate pre-effect authorization,
  immutable request/receipt reconciliation, and fail-closed unavailable
  receipts.
- Added owner-encrypted production SQLite composition and monotonic loop budget
  and evidence accounting.
- Bound passing diagnostic receipt IDs into the same changeset preview as
  ordinary signed verifier evidence.
- Added diagnostic-only execution with no owner mutation and modifying
  execution with post-apply reruns before local commit.
- Added pristine pre-edit performance capture, sanitized artifact binding,
  integer comparison, and natural percentage threshold policy.
- Packaged the helper as a release-owned expert asset and added digest-bound
  active-release-relative sandbox mounts.
- Added Python-aware no-shell stack, trace, crash, and performance execution.
- Added read-only Console and Shell evidence surfaces.

## Explicitly not completed

- Distributed service tracing across an integration environment.
- A newly built and installed signed release proving this composition.
- Complete installed diagnostic qualification rows on both
  `compat-cpu-16gb` and `full-reference-workstation`.
- AppArmor host-policy installation, aggregate qualification, soak, and human
  review.

## Architecture and decisions

ADR 0218 makes the natural selector Core-owned, makes baseline capture precede
generation, and makes helper resolution relative to the verified installed
release. ADRs 0175 and 0176 remain authoritative for sandbox, artifact,
sanitizer, and resource boundaries.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/runtime_diagnostic_intent.py` | Natural policy and exact baseline planning |
| `src/fam_os/core/engineering/runtime_diagnostic_service.py` | Live authority and durable execution |
| `src/fam_os/product/runtime_diagnostic_api.py` | Owner-scoped candidate/post-apply composition |
| `src/fam_os/adapters/sqlite/engineering_runtime_diagnostic.py` | Immutable request and receipt persistence |
| `src/fam_os/adapters/bubblewrap/diagnostics.py` | Authorized receipts and baseline capture |
| `src/fam_os/adapters/diagnostics/tool.py` | Python/native no-shell diagnostic target runner |
| `src/fam_os/product/release_assembly.py` | Release-owned helper packaging and signed mount |
| `src/fam_os/product/natural_engineering_execution.py` | Same-lifecycle baseline, diagnostic, and checkpoint wiring |
| `src/fam_os/product/natural_engineering_api.py` | Diagnostic-only and post-apply lifecycle paths |
| `src/fam_os/console/static/natural_engineering.js` | Owner-visible diagnostic outcomes |
| `src/fam_os/shell/engineering_loop_contracts.py` | Read-only typed diagnostic query |
| `tests/integration/test_natural_runtime_diagnostics.py` | Natural lifecycle proof |

## Public interfaces

New interfaces are `RuntimeDiagnosticPhase`, `RuntimePerformanceMode`,
`RuntimePerformanceBaseline`, `RuntimeDiagnosticIntentPolicy`,
`RuntimeDiagnosticService`, `SQLiteRuntimeDiagnosticStore`,
`ProductRuntimeDiagnosticApi`, and Shell operation `runtime_diagnostics`.
`ToolchainMount` adds a backward-compatible `source_kind` with
`installed_release` resolution.

## Validation

```bash
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_runtime_diagnostics tests.unit.test_runtime_diagnostic_composition tests.integration.test_runtime_diagnostics_exit tests.integration.test_natural_runtime_diagnostics tests.integration.test_natural_engineering_checkpoint tests.unit.test_product_engineering_loop_api tests.unit.test_engineering_execution tests.unit.test_release_bundle tests.unit.test_installed_integration_recipes tests.integration.test_console_engineering_loop tests.unit.test_fam_shell_engineering_loop_transport tests.unit.test_shell_engineering_projection tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -q"
larry run "PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests/architecture -q"
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
node --check src/fam_os/console/static/natural_engineering.js
git diff --check
```

Result: the focused product, physical sandbox, natural lifecycle, release,
Console, Shell, and schema suite passed 86 tests. The architecture suite passed
41 tests. All 413 schema artifacts, JavaScript syntax, and `git diff --check`
passed. Full logs:

- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T11-51-04-193Z.log`
- `/home/demimagic/.larry/-home-demimagic-Desktop-NewLLM-FAM_OS/runs/run-2026-07-19T11-51-04-222Z.log`

During implementation, routing `strace` through the Python/native helper first
exceeded the old 4 KiB fixture capture bound. The fixture was corrected to the
production 1 MiB bounded capture while retained sanitized evidence remains
separately bounded; the output-flood fixture still forces a 512-byte failure.

## Evidence and artifacts

- `tests/integration/test_natural_runtime_diagnostics.py`
- `tests/integration/test_runtime_diagnostics_exit.py`
- `tests/unit/test_runtime_diagnostic_composition.py`
- `tests/unit/test_engineering_execution.py`
- `docs/decisions/0218-natural-runtime-diagnostics-use-pristine-baselines-and-release-owned-tools.md`

## Known limitations and risks

- The trace recipe is local process-tree evidence, not distributed tracing.
- Physical source execution cannot substitute for installed signed evidence.
- Performance timing remains host-sensitive; both required profiles must use
  identical recipes, limits, and profile identities during qualification.

## Operational notes

No live service, installed release, owner repository, host policy, sysctl,
package, or external system was changed. Physical fixtures used temporary
candidate workspaces only.

## Recommended next entry point

Compose distributed trace collection with Phase 27.13 service environments,
then build one signed candidate containing this source, run every installed
diagnostic row on both profiles, and only then check Phase 27.11.
