# ADR 0043: Use privacy-bounded layered Linux application discovery

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Represent installed applications, launch metadata, current-user processes,
windows, focus, and discovery issues in provider-neutral Application Fabric
contracts.

Read visible freedesktop desktop entries as launch metadata, current-user procfs
identity without command lines/environments, and X11 EWMH identity/focus through
shell-free `xprop`. Exclude window titles by default. Correlate only unique
executable or `StartupWMClass` matches and preserve ambiguity as unknown.

Report non-X11/Wayland window discovery as explicitly unavailable until a
supported desktop semantic or accessibility provider exists. Do not use screen
observation or input control as an implicit discovery fallback.

## Consequences

- FAM can know which applications and high-level windows are present with low
  context and privacy cost.
- Launch commands are data only and carry a shell-safety classification; this
  step introduces no launch action authority.
- Process discovery avoids common secret-bearing sources such as
  `/proc/*/cmdline` and `/proc/*/environ`.
- X11 works on the current reference workstation; Wayland fidelity is explicitly
  degraded rather than overstated.
- Later accessibility/native providers can enrich the same identities without
  changing Core policy.

## Evidence

- `src/fam_os/applications/discovery.py`
- `src/fam_os/adapters/linux/processes.py`
- `src/fam_os/adapters/linux/desktop_entries.py`
- `src/fam_os/adapters/linux/x11_windows.py`
- `src/fam_os/adapters/linux/application_discovery.py`
- `tests/unit/test_linux_application_discovery.py`
- `tests/integration/test_linux_application_discovery_live.py`
- `docs/protocols/LINUX_APPLICATION_DISCOVERY.md`
