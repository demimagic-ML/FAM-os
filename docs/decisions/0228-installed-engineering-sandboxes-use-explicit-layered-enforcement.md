# ADR 0228: Installed engineering sandboxes use explicit layered enforcement

Status: Accepted

## Context

The installed natural-engineering lifecycle reached the real Python and Node
toolchains but failed or stalled at host boundaries that component tests did
not reproduce. Bubblewrap could not configure loopback unless the installed
AppArmor user-namespace profile was explicitly selected. Transient user scopes
could remain visible after completion when not collected. A redundant
`RLIMIT_AS` constrained V8 even though the scope already enforced `MemoryMax`,
and a sixteen-process scope was too small for the qualified Node test runner.

## Decision

Production engineering commands execute in a collected transient systemd user
scope. When the installed `fam-os-userns` profile is selected, the scope invokes
Bubblewrap through the fixed `/usr/bin/aa-exec -p fam-os-userns` boundary.
Bubblewrap remains responsible for namespaces, mounts, and network isolation;
systemd remains responsible for cgroup memory and process ceilings.

The subprocess pre-exec limiter retains CPU, output, and file limits but does
not also impose `RLIMIT_AS` when a cgroup `MemoryMax` is active. The qualified
Node/TypeScript engineering profile permits 32 processes, which is the measured
minimum tier that lets the real Node test worker start while retaining a hard
cgroup ceiling.

## Consequences

- Installed toolchains use the named host profile rather than depending on
  ambient AppArmor attachment.
- Completed scopes are collected and do not accumulate as runtime state.
- Memory authority has one primary enforcing owner, avoiding conflicting V8
  address-space behavior.
- Node verification remains bounded but can start its real worker processes.
- Missing `aa-exec`, the named profile, systemd scope creation, or Bubblewrap
  still fails closed.

## Alternatives considered

- Disable network namespaces: rejected because it weakens the sandbox to make
  the test pass.
- Remove cgroup limits and retain only rlimits: rejected because the product
  requires externally observable process-group enforcement.
- Raise all process profiles globally: rejected because only the measured
  Node/TypeScript profile needed the larger ceiling.

## Evidence

- `src/fam_os/adapters/bubblewrap/engineering.py`
- `src/fam_os/adapters/bubblewrap/process.py`
- `src/fam_os/adapters/bubblewrap/rlimits.py`
- `src/fam_os/product/candidate_engineering_api.py`
- `tests/unit/test_engineering_execution.py`
- `tests/unit/test_sandbox_process_capture.py`
- `tests/integration/test_polyglot_engineering_sandbox.py`
- `artifacts/product/phase30/natural-cli-acceptance-20260719-01/evidence.json`
