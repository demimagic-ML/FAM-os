# Handoff 0050: Cross-application acceptance

**Date:** 2026-07-16  
**Plan step:** Phase 5.12  
**Status:** Complete  
**Previous handoff:** `0049-required-application-action-safety.md`

## Objective

Prove the Phase 5 Application Fabric through real FAM Shell user flows and live
adapters, including explicit approval, deterministic verification, audit,
integration-level measurements, and successful degradation when MCP is absent.

## Scope completed

- A thread-safe Core request broker for live authenticated local connectors.
- Explicit exact-file versus trailing-slash workspace-directory scope semantics,
  including parsed file authorities and dot-segment rejection.
- A real Shell-to-Core README summary using an unmodified Zenity AT-SPI
  observation, official-SDK MCP resource, scoped file content, and local
  `qwen3:1.7b` through the Ollama runtime.
- One exact bounded Python unittest through the allowlisted shell-free tool
  adapter, released only on zero exit.
- A real isolated VS Code extension session with active-editor observation,
  revision-bound `Before` to `After` preview, Shell approval, Core confirmation,
  trusted live hash/version verification, reversible metadata, and two durable
  action-audit events.
- A second README run with no MCP process or capability, explicitly marked
  reduced fidelity and completed successfully.
- Per-operation context bytes, latency, FAM-process CPU/RSS/I/O plus per-level
  reliability aggregates and a separate full host/GPU inventory snapshot.
- Canonical JSON artifact with all Shell transcripts and a machine-checked exit
  gate.

## Explicitly not completed

- General natural-language planning; the acceptance gateway allowlists exactly
  three reviewed prompts and cannot become a second Core.
- Saving the VS Code buffer to disk; the verified action is editor-buffer state.
- Full cgroup attribution for VS Code, Ollama, and MCP provider processes, which
  belongs to Phase 7 telemetry and scheduling.
- Repeated soak trials or production reliability claims.

## Architecture and decisions

ADR 0050 freezes new adapter breadth until the real vertical proves the
contracts. The composition uses the existing Shell wire and Core lifecycle, not
a UI stub. `ConnectorRequestBroker` closes the missing outbound live-connector
seam. Workspace roots are hierarchical only when explicitly encoded with a
trailing slash; exact file scopes remain exact. Model summary output remains
completed rather than verified, while the deterministic test and editor action
are verified.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/applications/transport/broker.py` | Live connection ownership and correlated Core requests. |
| `src/fam_os/applications/transport/endpoint.py` | Reports authenticated connections to connection-aware dispatchers. |
| `src/fam_os/core/lifecycle/application_authorization.py` | Safe exact/directory file-resource admission. |
| `src/fam_os/core/lifecycle/action_execution_service.py` | De-duplicates overlapping pre/postcondition audit IDs. |
| `connectors/vscode/src/editor/provider.ts` | Explicit trailing-slash workspace scopes. |
| `src/fam_os/application_acceptance/` | Small Core, adapter, workflow, metrics, Shell, and reporting composition modules. |
| `tools/run_phase5_acceptance.py` | Bounded acceptance entry point. |
| `tests/unit/test_application_acceptance.py` | Exit-gate and reliability/resource aggregation tests. |
| `tests/integration/test_application_connector_broker.py` | Live broker correlation proof. |
| `tests/integration/test_vscode_connector_live_acceptance.py` | Opt-in isolated real-extension observation. |
| `artifacts/application_fabric/phase5_acceptance.json` | Canonical raw acceptance evidence and Shell transcripts. |
| `docs/operations/CROSS_APPLICATION_ACCEPTANCE.md` | Scenarios, measurements, operation, and interpretation. |
| `docs/decisions/0050-vertical-application-acceptance-before-more-adapters.md` | Durable vertical-first decision. |

## Public interfaces

- `ConnectorRequestBroker.await_connector`, `observe`, `prepare_action`, and
  `execute_action`.
- `AcceptanceReport`, `ScenarioEvidence`, `OperationMeasurement`, and
  `IntegrationLevel`.
- `Phase5AcceptanceRunner` and `tools/run_phase5_acceptance.py`.
- Trailing-slash `file:` registration scopes denote directories; other resource
  scopes remain exact.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_application_acceptance tests.unit.test_core_action_execution tests.integration.test_application_connector_broker
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python tools/run_phase5_acceptance.py --output artifacts/application_fabric/phase5_acceptance.json
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools connectors/vscode/test
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
cd connectors/vscode && npm test
PYTHONPATH=src:. FAM_OS_RUN_VSCODE_LIVE=1 /tmp/fam-os-mcp-venv/bin/python -m unittest tests.integration.test_vscode_connector_live_acceptance
python3 <AST module/function size gate>
```

Result: the measured acceptance exited zero with `exit_gate_passed=true`. Four
Shell sessions succeeded; the bounded test and native edit were verified, and
the reduced-fidelity summary succeeded without MCP. Accessibility completed 2/2
operations, MCP 1/1, deterministic OS/tool 5/5, and native semantic 4/4. The
native edit emitted two action-audit events. Both full Python environments
passed all 551 tests with three expected environment-dependent skips each. The
opt-in real VS Code test passed separately in 3.476 seconds. All 42 schemas,
seven Node tests, the cross-language connector transport, eight connector
schemas, and compileall passed. All 316 implementation modules remained within
300 lines per module and 50 lines per function. Larry indexed 779 files / 2,419
symbols with 10,991 nodes / 41,791 edges and clean health; the persisted code
graph was refreshed to the same 10,991-node / 41,791-edge source view.

The accepted host snapshot recorded 24 logical CPUs, 67,017,834,496 bytes of
RAM, 36,215,312,384 available bytes, an RTX 5080 with 16,303 MiB VRAM, and a
2,013,991,550,976-byte workspace filesystem. Run-specific totals are preserved
in the artifact rather than asserted as stable machine facts.

## Evidence and artifacts

- `artifacts/application_fabric/phase5_acceptance.json`
- `docs/operations/CROSS_APPLICATION_ACCEPTANCE.md`
- `docs/decisions/0050-vertical-application-acceptance-before-more-adapters.md`
- `tests/integration/test_vscode_connector_live_acceptance.py`

## Known limitations and risks

- One successful run is integration evidence, not a statistical reliability
  claim; the report schema exposes attempts and success rates for future repeats.
- Provider-process resource consumption is not fully attributed by the
  FAM-process measurements.
- The local summary has no semantic verifier and is correctly not marked
  verified.
- An isolated VS Code launch dominates current native latency.
- Distribution GI is appended only when the MCP virtual environment cannot
  import GI directly; production packaging must declare both dependencies.

## Operational notes

All application windows, Unix sockets, MCP processes, temporary profiles,
temporary files, and audit directories were removed. The launcher terminates
only current-user processes whose command line contains the unique temporary
profile root. No normal VS Code profile or repository source file was modified.
The Ollama service remains the pre-existing user service; `qwen3:1.7b` used its
normal keep-alive.

## Recommended next entry point

Begin Phase 6.1. Read `src/fam_os/experts/contracts.py`, manifest schemas and
fixtures, routing/expert capability references, the Phase 5 acceptance
capability inventory, and ADR 0016. Finalize the expert capability namespace and
manifest contract before implementing the local registry in Phase 6.2.
