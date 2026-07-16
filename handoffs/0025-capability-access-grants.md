# Handoff 0025: Capability-based device and filesystem access

**Date:** 2026-07-16  
**Plan step:** Phase 3.4  
**Status:** Complete  
**Previous handoff:** `0024-applied-resource-limits.md`

## Objective

Give an authenticated owner of a FAM user service narrowly allowlisted,
expiring filesystem and device capabilities without admitting arbitrary Linux
paths into Supervisor policy, and prove the resulting namespace on the live
reference workstation.

## Scope completed

- Added opaque namespaced resource IDs and typed filesystem/device kinds.
- Added read, write, and read/write modes with descriptor-owned allowlists.
- Scoped each grant to authority, principal, session, owned service, resource,
  issue time, and expiry.
- Required an independently injected device/filesystem capability authority.
- Rejected unknown resources, wrong owners, expired grants, mode/kind mismatch,
  and mismatched adapter evidence.
- Made grant IDs single-use even after revocation.
- Added a provider-neutral resource catalog and active/revoked grant registry.
- Added an access-enforcement port and service-definition projection port.
- Added trusted Bubblewrap mappings that keep raw source/destination paths out
  of the domain grant.
- Restricted filesystem targets to `/access` and device targets to `/dev`.
- Excluded expired and other-service grants from service projection.
- Rejected write-only access because Bubblewrap cannot enforce that mode.
- Added optional explicit AppArmor profile selection to user-systemd start.
- Added declare-before-start lifecycle composition for grant provisioning.
- Moved device/filesystem capabilities from planned to implemented in the
  canonical Supervisor boundary.
- Proved allowlist-only filesystem and harmless character-device access inside a
  real Bubblewrap/systemd service, then proved unit cleanup.
- Added architecture documentation, ADR 0026, Master Plan status, and this handoff.

## Explicitly not completed

- No arbitrary path or device-string grant API was added.
- No root helper, system service, host-wide AppArmor change, or GPU mutation was used.
- No live NVIDIA device was opened; device projection is unit-tested and the live
  proof uses a harmless `/dev/null` alias.
- No hot unmount is claimed. A running mount namespace retains launch-time binds
  until the owned service is stopped; Phase 3.6 owns coordinated safe termination.
- No durable grant/resource registry or external authentication transport exists yet.
- No dedicated FAM AppArmor profile is installed yet; packaging belongs to Phase 14.
- No audit event is emitted yet; Phase 3.5 is next.

## Architecture and decisions

ADR 0026 keeps access intent provider-neutral. Callers name an opaque allowlisted
resource; only the Bubblewrap adapter knows the trusted Linux paths. This avoids
turning a permission grant into a general host-path API.

The base `ServiceDefinition` remains the ownership-registry identity. The
systemd lifecycle invokes a `ServiceDefinitionProjector` immediately before
start, and the projector selects only active grants for that service. Resource
limits and environment are preserved exactly.

Filesystem mappings are rooted under `/access`; device mappings remain under
`/dev`. Bubblewrap supplies minimal runtime, proc, device, and temporary trees,
then adds exact bindings. User namespaces remain subject to host AppArmor policy;
the adapter can select a named preinstalled profile but cannot modify that policy.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/supervisor/access_contracts.py` | Opaque resource, grant, mode, and evidence contracts |
| `src/fam_os/supervisor/access_registry.py` | Resource allowlist and single-use grant state |
| `src/fam_os/supervisor/access_control.py` | Scope, authority, ownership, policy, and evidence admission |
| `src/fam_os/supervisor/ports/access.py` | Access enforcement port |
| `src/fam_os/supervisor/ports/lifecycle.py` | Service-definition projector port |
| `src/fam_os/supervisor/lifecycle.py` | Declare-before-start ownership flow |
| `src/fam_os/supervisor/boundary.py` | Implemented access capabilities |
| `src/fam_os/adapters/bubblewrap/service_access.py` | Trusted path mapping and namespace projection |
| `src/fam_os/adapters/systemd/settings.py` | Explicit AppArmor profile setting |
| `src/fam_os/adapters/systemd/commands.py` | Transient-unit AppArmor property |
| `src/fam_os/adapters/systemd/lifecycle.py` | Projection before systemd start |
| `tests/unit/test_service_access_control.py` | Admission, revocation, replay, and evidence tests |
| `tests/unit/test_bubblewrap_service_access.py` | Projection, isolation, expiry, path, and mode tests |
| `tests/hardware/bubblewrap_service_access_smoke.py` | Live filesystem/device namespace proof |
| `docs/architecture/CAPABILITY_ACCESS_GRANTS.md` | Enforcement and revocation boundary |
| `docs/decisions/0026-opaque-access-grants-and-bubblewrap-projection.md` | Architecture decision |

## Public interfaces

- `AccessResourceKind`
- `AccessMode`
- `AccessEvidenceStatus`
- `AccessResourceDescriptor`
- `ServiceAccessGrant`
- `AccessApplicationEvidence`
- `InMemoryAccessResourceCatalog`
- `InMemoryAccessGrantRegistry`
- `ServiceAccessAdapter`
- `ServiceAccessController`
- `ServiceDefinitionProjector`
- `BubblewrapAccessResource`
- `BubblewrapServiceAccessSettings`
- `BubblewrapServiceAccessAdapter`
- `SystemdUserSettings.apparmor_profile`
- `OwnedServiceLifecycle.declare`

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_service_access_control \
  tests.unit.test_bubblewrap_service_access \
  tests.unit.test_supervisor_boundary \
  tests.unit.test_systemd_lifecycle \
  tests.unit.test_systemd_commands
```

Result: all 23 focused tests passed in 0.001 seconds; 0 failures.

```bash
FAM_BUBBLEWRAP_ACCESS_SMOKE=1 PYTHONPATH=src:. \
  python3 -m unittest tests.hardware.bubblewrap_service_access_smoke -v
```

Result: one live test passed in 0.042 seconds. The service read only the
allowlisted file, observed no `/home`, and wrote the allowlisted `/dev/null`
alias. Post-cleanup state was `LoadState=not-found`, `ActiveState=inactive`.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: all 287 tests passed in 0.196 seconds, all 35 generated schemas matched,
and compilation completed successfully. The previous suite contained 274 tests.

An AST audit found no source module at or above 300 lines and no source function
at or above 50 lines.

```bash
npx -y larry-dev@latest setup
```

Result: Larry indexed 425 files, wrote four artifacts, refreshed its managed
agent block, and verified clean. The codebase graph was refreshed in fast mode
with 6,024 nodes and 18,054 edges.

## Evidence and artifacts

- `tests/hardware/bubblewrap_service_access_smoke.py`
- `docs/architecture/CAPABILITY_ACCESS_GRANTS.md`
- `docs/decisions/0026-opaque-access-grants-and-bubblewrap-projection.md`

## Known limitations and risks

- Resource and grant registries are process-local and lost on restart.
- Adapter mappings are trusted configuration and remain susceptible to host-path
  replacement risks that Phase 3.7 must model and test.
- Grant/revoke evidence describes launch-policy state; service start is the
  enforcement evidence, and revocation is not a hot unmount.
- The live host required the current named `vscode` AppArmor profile to authorize
  Bubblewrap user namespaces for the transient systemd service. Production must
  install and select a dedicated FAM profile without disabling the global restriction.
- Bubblewrap shares only declared mounts but is a policy mechanism, not by itself
  a complete hostile multi-tenant sandbox.

## Operational notes

Initial `ProtectHome`/`BindReadOnlyPaths` and unprofiled Bubblewrap probes did not
establish the required boundary. The latter failed under Ubuntu's AppArmor
user-namespace restriction. The successful live proof selected the already loaded
named profile inherited by this development session. No AppArmor file or sysctl
was changed.

The only live mutation was a temporary user service named `fam-phase34-smoke`.
It mapped `AGENTS.md` read-only and `/dev/null` as `/dev/fam-null`, slept briefly,
and was stopped and collected. No existing application, model, GPU, system unit,
or persistent host configuration changed.

## Recommended next entry point

Begin Phase 3.5. Read `src/fam_os/supervisor/boundary.py`,
`src/fam_os/supervisor/access_control.py`, and ADR 0026. Define immutable audit
event contracts and canonical encoding first, then add an append-only,
tamper-evident sink whose required-write failure fails the supervised operation
closed rather than silently dropping evidence.
