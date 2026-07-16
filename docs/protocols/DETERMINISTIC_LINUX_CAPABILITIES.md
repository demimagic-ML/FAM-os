# Deterministic Linux Capability Adapters

## Purpose

Phase 5.6 provides low-context, shell-free Linux capabilities for scoped files,
MIME identification, allowlisted D-Bus methods, desktop portals, and explicitly
configured tools. These are Application Fabric level-2 adapters: exact operating
system operations, not model imitation and not general shell access.

Raw adapter success is execution evidence only. Core permission, confirmation,
postconditions, audit, and final-result release remain separate.

## Bounded process transport

All external commands use `BoundedSubprocessRunner`. It requires an absolute
executable file, passes an argument tuple with `shell=False`, supplies only an
explicit environment, closes stdin, starts a separate process group, and bounds
time/stdout/stderr. Timeout or output overflow kills the entire group and
returns flags without releasing truncated provider output as success.

No D-Bus, portal, MIME, or tool module imports `subprocess` directly.

## Scoped file adapter

`ScopedFilePolicy` requires real absolute root directories and byte limits. Each
operation rejects lexical traversal, paths outside roots, missing intermediate
components, and symlink components. Reads use `O_NOFOLLOW`, accept regular files
only, and return size/SHA-256 with content opt-in.

Writes are two-stage:

1. `prepare_write` records target, current SHA-256 (or absence), proposed
   SHA-256, and exact byte count without mutation.
2. `apply_write` rechecks scope, content binding, and current hash, writes/fsyncs
   a same-directory temporary file, atomically replaces, fsyncs the directory,
   and rechecks the post-write hash.

Because no durable backup/undo token exists yet, the registry declares atomic
write irreversible with `ConfirmationPolicy.ALWAYS` and `file.sha256` as a
required postcondition. Phase 5.11 may add a verified reversal mechanism; this
adapter does not claim one early.

Path checking plus `O_NOFOLLOW` protects the final component, but the current
path-based implementation is not a hardened hostile-concurrency sandbox: a
same-user adversary could race intermediate directories. A future hardened
service should use directory FDs/openat2 and supervisor isolation.

## MIME observation

The MIME adapter first runs absolute `/usr/bin/file --brief --mime-type -- PATH`
through the bounded runner and validates the returned MIME grammar. Provider
absence/failure falls back to Python extension mapping and labels the evidence
`extension_fallback`; it never pretends that fallback is magic-content proof.

## D-Bus adapter

Each D-Bus capability fixes bus, well-known destination, object path, interface,
member, primitive signature, parameter order, and JSON Schema. Callers select
only a configured capability ID. Primitive values are type/range checked and
passed to absolute `busctl` as distinct arguments. Complex container signatures
are intentionally unsupported initially. Failures discard stderr/provider text.

## Desktop portal adapter

The portal adapter separately prepares an allowlisted credential-free URI and
later invokes the exact `org.freedesktop.portal.OpenURI.OpenURI` call through
absolute `gdbus`. The action is registered irreversible and always-confirmed;
portal request acceptance is a required postcondition, not proof that user work
completed. A read-only Properties probe verifies portal availability without
opening anything.

## Tool adapter

A tool capability fixes an absolute executable, fixed arguments, optional
working directory, explicit environment, ordered parameter-to-flag mapping,
input JSON Schema, and text/JSON output kind. There is no arbitrary executable,
argument array, shell string, inherited secret environment, or unbounded output
surface. Malformed JSON and failed commands return content-free stable errors.

## Application Fabric registration

`build_deterministic_registration` publishes declarations as one OS-tool
connector. Built-in declarations cover file observation, atomic file write,
MIME observation, and portal OpenURI with explicit roots/schemes. Custom D-Bus
and tool declarations must supply the normal `CapabilityDescriptor` policy and
resource scopes.

## Live evidence

The reference-machine test performs only read-only/live-safe work: bounded file
hashing, MIME detection, `/usr/bin/sha256sum`, session D-Bus `Peer.Ping`, and a
desktop-portal version property probe. Portal OpenURI and durable file mutation
are tested only against fakes/temporary files, so validation does not open an
application or alter user data.
