# ADR 0176: Sanitizer virtual address space is separated from resident memory

Status: Accepted

## Context

Address, leak, and thread sanitizers reserve very large sparse virtual shadow
ranges while consuming much less resident memory. Applying the resident-memory
budget directly as `RLIMIT_AS` made clean sanitizer binaries fail before they
could run. Linkers also need more transient file space than the small amount of
diagnostic output allowed to leave the sandbox.

## Decision

Runtime diagnostic limits distinguish retained artifact bytes from transient
file bytes. `RLIMIT_FSIZE` uses the bounded transient-file budget; the sanitizer
still exports only the smaller sanitized artifact budget.

Crash/stack debugging and race/leak sanitizers may explicitly request
unbounded virtual address space. For those exact diagnostic kinds only, the
launcher omits `RLIMIT_AS`; systemd `MemoryMax`, swap denial, CPU, process,
file, output, and wall limits remain enforced. All other diagnostic kinds reject
this flag. The exception grants no host attachment or privilege.

## Consequences

- Sparse sanitizer shadow mappings can coexist with a bounded resident-memory
  cgroup.
- A model cannot request this exception for ordinary build, test, shell, trace,
  profile, or performance execution.
- Tool qualification must preserve host runtime incompatibility as unavailable.
- Existing sandbox requests retain their prior `RLIMIT_AS` behavior by default.

## Evidence

- `src/fam_os/verification/sandbox/contracts.py`
- `src/fam_os/adapters/bubblewrap/rlimits.py`
- `src/fam_os/core/engineering/diagnostics.py`
- `src/fam_os/adapters/bubblewrap/diagnostics.py`
- `tests/integration/test_runtime_diagnostics_exit.py`
