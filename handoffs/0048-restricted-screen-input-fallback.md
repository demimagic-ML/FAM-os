# Handoff 0048: Restricted screen and input fallback

**Date:** 2026-07-16  
**Plan step:** Phase 5.10  
**Status:** Complete  
**Previous handoff:** `0047-native-vscode-semantic-connector.md`

## Objective

Implement the last-resort Application Fabric level for applications that lack
adequate semantic, deterministic-tool, or accessibility surfaces, while making
pixel observation and simulated input narrower and more conservative than every
higher-fidelity integration level.

## Scope completed

- Provider-neutral application, process, and window-scoped screen contracts.
- Independent capture and input availability so observation does not imply an
  injection backend or action authority.
- Exact scene IDs over window identity, source geometry, and PNG SHA-256.
- Source-pixel, encoded-pixel, PNG-byte, media-type, and active-window bounds.
- Two-stage action preparation/execution with full-scene checks before proposal
  and again after confirmation, plus an exact instruction digest.
- An initial input allowlist containing one left click or one chord of at most
  four reviewed keys; no text, clipboard, drag, scroll, or generic key surface.
- X11 active-window/process/geometry inspection through the existing bounded,
  shell-free runner without reading titles.
- Optional Pillow capture that rejects oversized source windows before pixel
  allocation and downsizes before bounded PNG encoding.
- Minimal `libX11`/`libXtst` binding with XTest extension probing, per-operation
  display lifecycle, and provider-side identity/focus/geometry revalidation.
- Explicit unavailable behavior on Wayland, headless sessions, missing Pillow,
  missing XTest, provider mismatch, stale scenes, or bound violations.
- Metadata-only live X11 validation with no pixel capture and no input event.

## Explicitly not completed

- Wayland compositor, PipeWire, xdg-desktop-portal ScreenCast/RemoteDesktop, or
  user-session portal authorization.
- Full-desktop capture, background-window input, arbitrary text, clipboard,
  drag, double-click, scrolling, or arbitrary key codes.
- OCR, vision inference, image persistence, or ambient screenshot collection.
- A claim that input invocation or an immediate postframe proves task success.
- Cross-level safety audit composition, which is Phase 5.11.

## Architecture and decisions

ADR 0048 makes level 4 exact-active-window-only and safety-first. Provider SDKs
remain behind separate inspector, capture, and input seams. Core still owns
permission, proposal, confirmation, verification, final release, and audit.
Input is declared irreversible and always-confirmed. Exact matching deliberately
rejects animated or transient scenes rather than using an ambiguous visual
similarity threshold.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/applications/screen_input.py` | Provider-neutral target, frame, observation, instruction, proposal, and evidence values. |
| `src/fam_os/applications/__init__.py` | Public Application Fabric exports. |
| `src/fam_os/adapters/linux/screen_input/bridge.py` | Bounds, scene lifecycle, allowlists, and evidence. |
| `src/fam_os/adapters/linux/screen_input/policy.py` | Conservative capture and input policy. |
| `src/fam_os/adapters/linux/screen_input/ports.py` | Replaceable provider boundary. |
| `src/fam_os/adapters/linux/screen_input/types.py` | Adapter-owned provider values. |
| `src/fam_os/adapters/linux/screen_input/catalog.py` | Registry declarations and exact resource scopes. |
| `src/fam_os/adapters/linux/screen_input/x11_inspector.py` | Bounded active X11 identity and geometry inspection. |
| `src/fam_os/adapters/linux/screen_input/pillow_capture.py` | Optional bounded PNG capture. |
| `src/fam_os/adapters/linux/screen_input/xtest_input.py` | Minimal XTest click and key injection. |
| `src/fam_os/adapters/linux/screen_input/x11_provider.py` | Concrete provider composition and final target recheck. |
| `tests/unit/test_screen_input_fallback.py` | Contracts, bounds, stale-scene, allowlist, and registration tests. |
| `tests/unit/test_x11_screen_input_provider.py` | Parser, downscale, target recheck, and coordinate tests. |
| `tests/architecture/test_screen_input_boundary.py` | Dependency and provider-import confinement. |
| `tests/integration/test_x11_screen_input_live.py` | Mutation-free live X11 metadata/backend probe. |
| `docs/protocols/RESTRICTED_SCREEN_INPUT_FALLBACK.md` | Current boundary and operational semantics. |
| `docs/decisions/0048-restricted-screen-input-fallback.md` | Durable restriction decision. |

## Public interfaces

- `ScreenTarget`, `ScreenFrame`, `ScreenObservation`, `RelativeScreenPoint`,
  `ScreenInputInstruction`, `ScreenInputProposal`, and `ScreenInputEvidence`.
- `ScreenInputBridge`, `ScreenInputPolicy`, and `ScreenInputProvider`.
- `X11InspectorSettings`, `X11WindowInspector`, `PillowPngCapture`,
  `XTestInput`, and `X11ScreenInputProvider`.
- Capabilities `linux.screen.observe_active_window` and
  `linux.input.control_active_window` over transport kind `screen_input`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_screen_input_fallback tests.unit.test_x11_screen_input_provider tests.architecture.test_screen_input_boundary tests.integration.test_x11_screen_input_live
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools connectors/vscode/test
python3 <AST module/function size gate>
larry index . && larry health .
```

Result: all 15 focused tests passed. Both full Python environments passed all
532 tests with two expected environment-dependent skips each. The live X11 test
resolved the current focused window's identity and geometry, confirmed XTest,
and confirmed Pillow only where installed, without capturing pixels or sending
input. All 40 schema artifacts matched and compileall succeeded. All 285 Python
implementation modules remained at or below 300 lines per module and 50 lines
per function. Larry indexed 734 files / 2,240 symbols with 10,477 nodes / 38,529
edges and clean health; the persisted code graph was refreshed to the same
10,477-node / 38,529-edge source view.

## Evidence and artifacts

- `docs/protocols/RESTRICTED_SCREEN_INPUT_FALLBACK.md`
- `docs/decisions/0048-restricted-screen-input-fallback.md`
- `tests/integration/test_x11_screen_input_live.py`

## Known limitations and risks

- An X11 rectangle can contain an overlapping notification or always-on-top
  surface even when the intended window owns the rectangle.
- Exact scene hashes reject benign animation, video, blinking cursors, and other
  changing pixels; this is intentional safe degradation.
- Input can race with desktop changes after the final recheck, and an application
  can ignore a successfully injected event.
- Immediate before/after pixels may be equal or may not express the intended
  semantic result.
- Pillow and XTest are optional environment capabilities, not required Core
  dependencies.

## Operational notes

No screenshot was captured, saved, logged, or sent to a model during live
validation. No pointer or key event was injected. Bounded `xprop`/`xwininfo`
processes exited normally and no service or socket was left running.

## Recommended next entry point

Begin Phase 5.11. Read `fam_os.applications.actions`, Core application-step and
confirmation services, Phase 5.2 transport event handling, Supervisor audit
contracts, and adapters from levels 1-4. Define one provider-neutral action
safety envelope and audit linkage before changing any individual connector.
