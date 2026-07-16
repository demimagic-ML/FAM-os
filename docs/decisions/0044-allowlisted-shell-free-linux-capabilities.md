# ADR 0044: Make deterministic Linux capabilities exact and shell-free

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Implement files, MIME, D-Bus, portals, and tools as separate allowlisted
Application Fabric adapters over one bounded shell-free process transport.
Require absolute executables, exact schemas/argument mappings, explicit
environments, resource scopes, time/output limits, and content-free failures.

Split file mutation into proposal and apply stages with exact content/current
hash binding, atomic replacement, and post-write hash evidence. Until durable
undo exists, declare it irreversible and always-confirmed. Treat D-Bus, portal,
and tool success as raw evidence requiring later Core postconditions rather than
verified action results.

## Consequences

- Models cannot turn a tool request into an arbitrary command or shell string.
- Deterministic operations reduce tokens while retaining exact audit inputs.
- File writes reject stale state and partial replacement but are not yet
  reversible or hardened against hostile same-user directory races.
- D-Bus container signatures remain unsupported until a typed encoder is added.
- Live tests can exercise useful OS integration without changing desktop state.

## Evidence

- `src/fam_os/adapters/linux/bounded_command.py`
- `src/fam_os/adapters/linux/scoped_files.py`
- `src/fam_os/adapters/linux/mime_types.py`
- `src/fam_os/adapters/linux/dbus_calls.py`
- `src/fam_os/adapters/linux/desktop_portal.py`
- `src/fam_os/adapters/linux/tools.py`
- `src/fam_os/adapters/linux/deterministic_catalog.py`
- `tests/integration/test_deterministic_linux_capabilities_live.py`
- `docs/protocols/DETERMINISTIC_LINUX_CAPABILITIES.md`
