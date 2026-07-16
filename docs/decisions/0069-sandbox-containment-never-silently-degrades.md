# ADR 0069: Sandbox containment never silently degrades

**Status:** Accepted  
**Date:** 2026-07-16

## Context

The original launcher applied useful rlimits, but buffered unlimited child
output before truncation and did not limit process creation. Bubblewrap startup
failure also appeared as an ordinary completed child with exit code one, which
could be confused with a rejected candidate.

## Decision

Required Bubblewrap isolation fails closed when the binary is absent or cannot
establish namespaces. Process-only execution remains explicitly labeled and
cannot satisfy a Bubblewrap requirement. Output is drained incrementally into
fixed caps, timeout kills the whole process group, RLIMIT_NPROC is added, the
environment is cleared, and only declared variables are restored inside the
namespace.

## Consequences

- Output floods cannot make retained buffers grow without bound.
- Descendants are terminated with timed-out work.
- Infrastructure failure is distinguishable from candidate failure.
- This workstation currently reports sandbox unavailability because namespace
  creation is denied; verified hostile-code execution must remain withheld.
- VM-grade isolation and syscall filtering are not falsely claimed.
