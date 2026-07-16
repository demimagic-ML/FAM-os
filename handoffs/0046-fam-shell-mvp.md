# Handoff 0046: FAM Shell MVP

**Date:** 2026-07-16  
**Plan step:** Phase 5.8  
**Status:** Complete  
**Previous handoff:** `0045-linux-accessibility-bridge.md`

## Objective

Build the first usable FAM_OS interface for Ask, selected context, plan/progress,
approval and denial, cancellation, and terminal results while keeping the Shell
an unprivileged client of Core rather than a second policy or model runtime.

## Scope completed

- Versioned Shell Ask, context, query, plan-step, approval, decision,
  cancellation, result, and session-snapshot contracts.
- Monotonic revision reducer with immutable identity/plan and absorbing terminal
  state.
- Context selection frozen during active work and capability union passed to
  Core without ambient resource content.
- Thin controller for Ask, refresh, exact approval/denial, and revision-bound
  cancellation.
- Color-free terminal renderer and command interface with explicit plan markers.
- Terminal control-sequence neutralization and content-free client failure UI.
- Installed `fam-shell` entry point with configurable socket and timeout.
- Strict 1 MiB canonical JSON transport with five registered Shell schema roots.
- Client endpoint ownership/mode checks, private `0600` server socket,
  `SO_PEERCRED` authorization, exact correlation, and safe server errors.
- Core-side lifecycle/TaskResult-to-Shell projection that never gives the client
  candidate or policy internals.
- Real local-socket end-to-end test across terminal, controller, codec,
  authenticated server, dispatcher, and deterministic fake Core gateway.

## Explicitly not completed

- A production composition of all Core admission/routing/execution services
  behind `ShellCoreGateway`; Phase 5.8 supplies the gateway contract and boundary.
- Background push/event streaming; MVP progress uses explicit `refresh`.
- Graphical Shell or administrative Console views.
- A real cross-application/model task through the Shell (Phase 5.12).

## Architecture and decisions

ADR 0046 makes the terminal and future GUI clients consumers of the same narrow
Core gateway. The Shell owns presentation state only. Core supplies safe progress,
approval summaries, and release-safe results. Commands bind to session revision
and approval ID. The endpoint authenticates the local Unix peer but does not
claim same-UID process isolation or package attestation.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/shell/contracts.py` | Versioned presentation and command values. |
| `src/fam_os/shell/ports.py` | Client/gateway boundary. |
| `src/fam_os/shell/state.py` | Monotonic snapshot reducer. |
| `src/fam_os/shell/controller.py` | UI-only interaction coordination. |
| `src/fam_os/shell/render.py` | Control-safe color-free rendering. |
| `src/fam_os/shell/terminal.py` | Small command interface. |
| `src/fam_os/shell/wire.py` | Strict typed bounded wire protocol. |
| `src/fam_os/adapters/shell/` | Unix client, server, dispatch, and CLI composition. |
| `src/fam_os/core/ingress/shell_views.py` | Trusted Core presentation projection. |
| `src/fam_os/schemas/catalog.py` | Five Shell document schemas. |
| `schemas/v1alpha1/fam.shell.*.schema.json` | Generated wire artifacts. |
| `tests/unit/test_fam_shell.py` | Contracts, controller, renderer, terminal tests. |
| `tests/unit/test_fam_shell_transport.py` | Codec and authenticated endpoint tests. |
| `tests/unit/test_core_shell_views.py` | Core projection tests. |
| `tests/integration/test_fam_shell_local_end_to_end.py` | Full local client path. |
| `tests/architecture/test_fam_shell_boundary.py` | Unprivileged client guard. |
| `tests/architecture/test_fam_shell_transport_boundary.py` | Adapter policy guard. |
| `docs/protocols/FAM_SHELL_MVP.md` | User, protocol, and safety guide. |
| `docs/decisions/0046-unprivileged-terminal-fam-shell.md` | Durable UI boundary. |

## Public interfaces

- `ShellCoreClient`, `ShellCoreGateway`, `ShellController`, and `TerminalShell`.
- Shell context, Ask, snapshot query, plan step, approval, decision,
  cancellation, result, and session snapshot types.
- `accepted_shell_snapshot` and `project_shell_snapshot`.
- `UnixShellCoreClient`, `UnixShellServer`, their configurations, and
  `ShellRequestDispatcher`.
- `fam-shell` installed command.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_fam_shell tests.unit.test_fam_shell_transport tests.unit.test_core_shell_views tests.integration.test_fam_shell_local_end_to_end tests.architecture.test_fam_shell_boundary tests.architecture.test_fam_shell_transport_boundary
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
printf 'help\nquit\n' | PYTHONPATH=src:. python3 -m fam_os.adapters.shell.cli
python3 <AST module/function size gate>
larry index . && larry health .
```

Result: all 22 focused tests passed. Both full environments passed all 512
tests; the MCP venv had one expected GI/AT-SPI skip and system Python had two
expected environment-dependent skips. All 40 schema artifacts matched, compile
succeeded, and 254 implementation modules had no file over 300 lines or
function over 50 lines. The actual terminal entry point displayed help and
exited successfully without contacting Core. Larry indexed 677 files / 2,071
symbols with 9,902 nodes / 36,227 edges and clean health. The persisted code
graph was refreshed with 9,929 nodes / 36,412 edges.

## Evidence and artifacts

- `docs/protocols/FAM_SHELL_MVP.md`
- `docs/decisions/0046-unprivileged-terminal-fam-shell.md`
- `tests/integration/test_fam_shell_local_end_to_end.py`
- `schemas/v1alpha1/fam.shell.snapshot.schema.json`

## Known limitations and risks

- Core production composition must implement `ShellCoreGateway`; the current
  full-path acceptance gateway is deterministic and fake-driven.
- Explicit polling is not live push progress.
- Same-UID authentication cannot distinguish an unauthorized same-user process.
- Terminal UI is the accessible MVP, not the final graphical Console.

## Operational notes

No persistent server or socket was left running. Tests used temporary private
directories and removed sockets. No model, connector, application, file, or
desktop action was invoked. The default client socket is
`$XDG_RUNTIME_DIR/fam-os/shell.sock`.

## Recommended next entry point

Begin Phase 5.9. Define a narrow editor connector capability set and SDK package,
then implement a VS Code extension and local connector service over the Phase
5.2 native transport. Start with bounded active-editor/selection/diagnostics
observations and version-bound workspace edits with deterministic post-edit
hash/text verification. Keep MCP optional and mapped behind the same registry.
