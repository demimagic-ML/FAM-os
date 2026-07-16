# ADR 0026: Use opaque access grants and adapter-owned Bubblewrap projection

**Status:** Accepted  
**Date:** 2026-07-16

## Context

FAM services need selected model stores, workspaces, accelerators, and other
devices without granting arbitrary host access or binding Supervisor policy to
Linux path syntax. Command construction alone is insufficient evidence that a
running service sees only the declared resources.

## Decision

Represent filesystem and device authority as expiring, single-use grants scoped
to an authenticated authority reference, principal, session, owned FAM service,
opaque resource ID, kind, and mode.

Resolve resource IDs through an injected provider-neutral allowlist before any
adapter call. Keep raw Linux source and destination paths in the Bubblewrap
adapter configuration only.

Project registered base service definitions at launch. Bubblewrap creates a
minimal mount namespace and binds only active grants for the exact service.
Constrain filesystem destinations to `/access`, device mappings to `/dev`, and
reject write-only access because the mechanism cannot enforce it.

Allow the systemd adapter to select a named AppArmor profile explicitly on hosts
where unprivileged user namespaces require that authorization. Never disable the
host-wide AppArmor restriction as an application workaround.

Treat revocation as removal from future projections. Immediate removal from an
already running namespace requires owned-service termination, which Phase 3.6
will coordinate.

## Consequences

- Domain grants remain portable and cannot smuggle arbitrary paths.
- Principal/session ownership and operation capability are independently checked.
- Grant identities cannot be replayed after revocation.
- Expired grants cannot enter a new service projection.
- Real filesystem and harmless character-device enforcement are proven live.
- A deployment needs Bubblewrap and, on restrictive hosts, an installed AppArmor
  profile that permits its user namespace.
- Revocation is not falsely described as a hot unmount.
- Adapter path configuration remains trusted local policy and must be included
  in the Phase 3.7 threat model.

## Alternatives considered

1. Put absolute paths directly in grants: rejected because callers could address
   arbitrary host resources and the domain would become Linux-specific.
2. Use systemd `BindReadOnlyPaths=` alone: rejected after a live probe did not
   produce the intended allowlist-only view for this user service.
3. Trust a recorded allowlist without a mount namespace: rejected because policy
   records would not constrain process filesystem visibility.
4. Disable AppArmor's user-namespace restriction globally: rejected because it
   weakens unrelated applications and exceeds FAM authority.
5. Claim revoke hot-removes mounts: rejected because Bubblewrap namespaces are
   fixed after launch; safe termination must be explicit.

## Evidence

- `src/fam_os/supervisor/access_contracts.py`
- `src/fam_os/supervisor/access_control.py`
- `src/fam_os/supervisor/access_registry.py`
- `src/fam_os/adapters/bubblewrap/service_access.py`
- `tests/unit/test_service_access_control.py`
- `tests/unit/test_bubblewrap_service_access.py`
- `tests/hardware/bubblewrap_service_access_smoke.py`
