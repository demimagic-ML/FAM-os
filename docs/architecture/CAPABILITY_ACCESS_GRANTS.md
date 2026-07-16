# Capability-based service access

## Invariant

An owned FAM service receives no host filesystem or device path from an access
grant. The Supervisor domain accepts only an opaque, namespaced resource ID that
already exists in an injected allowlist. A Linux adapter is solely responsible
for mapping that ID to trusted host and sandbox paths.

```text
authenticated caller + owned service
  -> scoped ServiceAccessGrant
  -> allowlist, ownership, mode, expiry, and authority checks
  -> provider-neutral grant registry
  -> trusted Linux resource mapping
  -> Bubblewrap service-definition projection
  -> systemd user service in the projected mount namespace
```

## Domain contracts

`AccessResourceDescriptor` declares:

- an opaque resource ID such as `filesystem.models` or `device.gpu-0`;
- whether the resource is a filesystem object or device;
- the exact modes the policy permits.

`ServiceAccessGrant` binds one grant ID to its authority reference, principal,
session, FAM-owned service, resource ID, kind, mode, issue time, and expiry. All
timestamps are timezone-aware. Grant IDs are single-use, including after
revocation, so a stale identity cannot be reactivated with new meaning.

Raw absolute paths fail resource-ID validation. Unknown resources, expired
grants, kind/mode mismatches, missing capability authority, and ownership
mismatches fail before the enforcement adapter is called.

## Linux projection

`BubblewrapServiceAccessAdapter` contains the trusted resource-ID-to-path map.
It also implements `ServiceDefinitionProjector`, allowing the systemd adapter to
start the registered base definition through a projected command without
putting Linux paths in Supervisor grants.

Every projected service receives:

- separate user, mount, PID, IPC, UTS, cgroup, and network namespaces;
- a read-only `/usr`, `/lib`, and optional `/lib64` runtime;
- a fresh `/proc`, minimal `/dev`, and temporary `/tmp`;
- no host home tree by default;
- only active, unexpired grants for that exact service ID.

Filesystem destinations must be below `/access`. Device mappings must stay
within `/dev`. Neither resource type can replace its sandbox root, and
destinations must be unique. Read maps to a read-only bind, filesystem
read/write maps to a bind, and device read/write maps to a device bind.
Bubblewrap cannot enforce write-only mounts, so write-only grants fail closed.

## AppArmor and systemd

Bubblewrap requires unprivileged user namespaces. On hosts that restrict their
creation through AppArmor, the transient user service must run under a named,
locally installed profile that authorizes `userns`. `SystemdUserSettings` accepts
that profile explicitly and emits `AppArmorProfile=` on the transient unit.

FAM_OS does not disable the host-wide user-namespace restriction. Packaging and
installation of a dedicated FAM profile belongs to Phase 14; until then a live
deployment must supply an already installed profile.

## Revocation boundary

Revocation removes a grant from future service projections and permanently
retires its grant ID. A mount namespace is fixed after process launch, so policy
revocation does not hot-unmount a resource from an already running service.
Callers must stop that owned service before revocation when immediate removal is
required. Phase 3.6 owns the formal safe-termination coordination and evidence.

The adapter's `GRANTED` and `REVOKED` evidence therefore describes application
to the launch policy, while the live service-start result proves namespace
enforcement. It is not a claim of hot revocation.

## Evidence

The focused tests prove domain rejection, ownership and expiry checks,
single-use grant IDs, exact evidence, service scoping, destination restrictions,
mode translation, and expired-grant exclusion.

The opt-in hardware smoke starts a real `fam-` user service. Inside the service,
an allowlisted repository file is visible at `/access/allowed.md`, `/home` is
absent, and an allowlisted `/dev/null` mapping is writable at
`/dev/fam-null`. Cleanup proves the transient unit is removed.
