# ADR 0076: Sandbox process count is a cgroup bound

**Status:** Accepted; supersedes the `RLIMIT_NPROC` portion of ADR 0069  
**Date:** 2026-07-16

## Context

`RLIMIT_NPROC` counts every process owned by the real Linux user. Applying a
small value before Bubblewrap startup denied namespace creation on an ordinary
desktop with more existing processes than the limit. It did not express a
sandbox-local process ceiling.

## Decision

FAM starts Bubblewrap inside a delegated transient systemd user scope with
`TasksMax`, `MemoryMax`, and zero swap. The scope preserves user-namespace setup
and bounds only the sandbox cgroup. Address-space, CPU, file-size, descriptor,
core, output, and wall-time bounds remain independently enforced.

## Consequences

Live Bubblewrap containment works without counting unrelated desktop processes.
The sandbox requires both Bubblewrap and the systemd user manager; either missing
or failing is explicit unavailability. No process-only fallback can satisfy the
declared containment capability.
