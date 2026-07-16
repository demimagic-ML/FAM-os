# Handoff 0043: Linux application discovery

**Date:** 2026-07-16  
**Plan step:** Phase 5.5  
**Status:** Complete  
**Previous handoff:** `0042-authenticated-mcp-core-ingress.md`

## Objective

Discover installed Linux applications, safe launch metadata, current-user
processes, windows, and focus without introducing application action authority
or privacy-heavy observation.

## Scope completed

- Provider-neutral application/process/window/focus/launch snapshot contracts.
- XDG desktop-entry precedence, visibility, identity, and shell-classified `Exec` parsing.
- Current-UID bounded procfs identity without cmdline or environment reads.
- X11 EWMH window/PID/class/focus discovery through shell-free `xprop`.
- Window titles excluded by default and explicit non-X11 degradation.
- Conservative unique executable/`StartupWMClass` correlation.
- Live reference-workstation read-only snapshot.

## Explicitly not completed

- Application launch, focus changes, signaling, control, accessibility, or screen input.
- Universal Wayland window enumeration; unsupported sessions degrade explicitly.
- Desktop-specific GNOME/KDE compositor extensions.
- Permission decisions based solely on discovered presence.

## Architecture and decisions

ADR 0043 separates low-cost presence/identity discovery from observation and
action. Launch entries are metadata only, shell involvement is classified, and
privacy-sensitive `/proc/*/cmdline`, `/proc/*/environ`, and window titles are not
captured by default. Ambiguous correlations remain unknown.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/applications/discovery.py` | Provider-neutral discovery contracts. |
| `src/fam_os/adapters/linux/processes.py` | Current-user procfs process discovery. |
| `src/fam_os/adapters/linux/desktop_entries.py` | Desktop-entry and launch metadata. |
| `src/fam_os/adapters/linux/x11_windows.py` | X11 window/focus provider and parsers. |
| `src/fam_os/adapters/linux/application_discovery.py` | Correlation and snapshots. |
| `src/fam_os/adapters/linux/desktop_environment.py` | Explicit XDG settings translation. |
| `tests/unit/test_linux_application_discovery.py` | Parser, privacy, degradation, and composition tests. |
| `tests/integration/test_linux_application_discovery_live.py` | Live machine snapshot. |
| `tests/architecture/test_linux_application_discovery_boundary.py` | Read-only layer guard. |
| `docs/protocols/LINUX_APPLICATION_DISCOVERY.md` | Protocol and privacy boundary. |
| `docs/decisions/0043-privacy-bounded-linux-application-discovery.md` | Durable decision. |

## Public interfaces

- `ApplicationDiscoverySnapshot` and component discovery values/issues.
- `LinuxProcessDiscovery` and pure proc status/stat parsers.
- `DesktopEntryDiscovery`, `DesktopEntrySettings`, and `parse_exec`.
- `X11WindowDiscovery`, X11 settings/results, and pure xprop parsers.
- `LinuxApplicationDiscovery` and explicit environment settings translation.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_linux_application_discovery tests.architecture.test_linux_application_discovery_boundary tests.integration.test_linux_application_discovery_live
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
python3 <AST module/function size gate>
larry index . && larry health .
```

Result: 10 focused/live tests and all 461 repository tests passed. The live
snapshot found 51 applications, 291 current-user processes, 18 X11 windows, one
focused/correlated window, zero issues, and no titles. All 35 schemas matched and
compile/AST gates passed. Larry indexed 616 files / 1,806 symbols with 8,278
nodes / 29,738 edges and clean health; the persisted graph was refreshed with
the same totals.

## Evidence and artifacts

- `docs/protocols/LINUX_APPLICATION_DISCOVERY.md`
- `docs/decisions/0043-privacy-bounded-linux-application-discovery.md`
- `tests/integration/test_linux_application_discovery_live.py`

## Known limitations and risks

- X11 global discovery is available on the reference session but is not portable
  to Wayland; desktop-specific providers are required there.
- Desktop `Exec` parsing intentionally rejects unusual embedded field codes and
  does not claim launchability guarantees.
- Basename/class correlation is conservative and may leave real applications
  unassigned; false negatives are preferred over false identity claims.

## Operational notes

Live probes were read-only `/proc`, desktop-file, and `xprop` calls. No process,
window, focus, file, setting, application, or desktop state was changed.

## Recommended next entry point

Begin Phase 5.6. Define deterministic capability bindings for scoped files,
MIME identification, desktop portals, D-Bus calls, and allowlisted tools. Keep
observation and mutation separate, validate all arguments, use no shell, and
return evidence suitable for Phase 5.11 postcondition/audit policy.
