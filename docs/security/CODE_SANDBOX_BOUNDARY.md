# Code sandbox security boundary

## Release rule

Untrusted generated code may be treated as verified only when the requested
verifier manifest requires `isolation.network-denied` and the sandbox returns
`bubblewrap` isolation. `process_limits` is an explicit development/degraded
mode; it is not a containment boundary and must not authorize release of
hostile code. Missing or failed namespace creation returns `unavailable`, never
a candidate test failure and never a silent downgrade.

## Bubblewrap boundary

The Linux adapter creates new user, PID, mount, IPC, UTS, cgroup, and network
namespaces through `--unshare-all`; drops every capability; clears inherited
environment; exposes only read-only `/usr`, `/lib`, and optional `/lib64`;
creates private `/proc`, `/dev`, and tmpfs `/tmp`; starts a new session; and dies
with its parent. The host home, working tree, credentials, display/session buses,
GPU devices, and network namespace are not mounted or inherited.

The child also receives hard address-space, CPU, file-size, open-file, and
core-dump rlimits. A delegated transient user scope enforces `TasksMax`, memory,
and zero swap without applying the real-user-wide `RLIMIT_NPROC`. Wall time is enforced by killing the complete process
group. Stdout and stderr are drained incrementally and retained only up to the
declared cap, preventing output-flood memory exhaustion.

## What this does not promise

Bubblewrap composes Linux kernel isolation; it is not a virtual machine. Kernel
vulnerabilities remain in scope, `/usr` binaries are readable/executable, and
there is currently no syscall seccomp allowlist. RLIMIT_NPROC is per real user
on Linux and is defense in depth, not a cgroup PID controller. High-risk or
multi-tenant hostile workloads require a stronger VM/container boundary before
their manifest can declare the corresponding capability.

No secrets may be placed in scripts, argv, the minimal environment, or mounted
paths. Candidate output remains untrusted until its family verifier passes.

## Current workstation evidence

`artifacts/verification/phase8.2/sandbox-security-probe.json` records live
Bubblewrap containment on this host. Home is absent, loopback access and system
writes fail, and the environment contains only declared values plus deterministic
`PWD=/tmp` and Python locale initialization. A delegated systemd user scope
enforces the process count. Independent launcher probes demonstrate bounded
333-byte output retention and process-group wall-time termination.
