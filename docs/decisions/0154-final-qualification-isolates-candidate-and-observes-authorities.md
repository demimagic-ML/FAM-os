# ADR 0154: Final qualification isolates candidate and observes authorities

Status: Accepted

## Context

The first Phase 23 installed and hardware runners found several harness defects
that could hide product failures: long temporary paths exceeded Linux AF_UNIX
limits, partial startup called `shutdown()` on a Console server that had never
served, owner Ollama could repopulate GPU cache during qualification, and
Factory plus uncertain-action subprocesses included the checkout in
`PYTHONPATH`.

The existing Console check also proved only that values were present. It did not
independently show that displayed CPU, memory, VRAM, storage, policy, catalog,
residency, permissions, audit, memory, and recovery values came from the live
providers that own those facts.

## Decision

Final installed qualification uses a short private runtime root, exposes only
the candidate-installed Python tree to product subprocesses, and validates
Console state against independent authorities.

- Product settings reject any runtime root whose Shell, Application Fabric, or
  MCP Unix socket would exceed Linux's 107-byte encoded path limit.
- Partial service cleanup closes an unserved Console without waiting on
  `shutdown()`; served Consoles retain graceful shutdown.
- Candidate services launch directly with the signed candidate tree as their
  only product `PYTHONPATH` and can emit all-thread stack traces on timeout.
- Factory qualification no longer imports the Phase 22 acceptance composition.
  It drives shipped product APIs from a small external qualification driver and
  records both candidate module identity and absence of the old import.
- The uncertain-action fault injector validates candidate identity before any
  mutation and receives no checkout source path.
- The full-GPU matrix continuously observes and evicts owner Ollama cache models
  during its bounded qualification window, while preserving the owner service.
- Console resource and expert values are cross-checked against host, cgroup,
  filesystem, NVIDIA, and Ollama telemetry. Repository-backed values must change
  with real terminal, permission, action-audit, and document-index operations.
  Missing-key recovery must remain keyless and mark unavailable providers
  explicitly.

## Consequences

- A missing candidate module cannot be silently supplied by checkout source.
- Startup failures surface their original cause instead of hanging in cleanup.
- Phase 23.4 and 23.6 now have direct installed evidence from both named hardware
  profiles and healthy/recovery Console states.
- Same-host remote evidence remains clearly insufficient for Phase 21.7 and the
  physical portion of 23.3.

## Alternatives considered

- Treating a root `fam_os` module-path check as sufficient was rejected because
  helper composition could still come from checkout tools.
- Reading only non-empty Console labels was rejected because stale or synthetic
  values could satisfy that test.
- Disabling the owner service for the entire matrix was rejected because the
  qualification must preserve the running owner product.
- Silently shortening arbitrary user runtime roots was rejected because it
  would change configured identity and hide an invalid deployment.

## Evidence

- `src/fam_os/product/service.py`
- `tools/phase23_installed_matrix/service.py`
- `tools/phase23_installed_matrix/factory_process.py`
- `tools/phase23_installed_matrix/factory_qualification.py`
- `tools/phase23_installed_matrix/factory_suite.py`
- `tools/phase23_installed_matrix/fault_window.py`
- `tools/phase23_installed_matrix/console_authority_scenario.py`
- `tools/phase23_hardware_matrix/owner_workload.py`
- `tools/phase23_hardware_matrix/telemetry.py`
- `tests/unit/test_product_service_startup_safety.py`
- `tests/unit/test_phase23_installed_scenario_matrix.py`
- `tests/unit/test_phase23_hardware_matrix.py`
- `artifacts/product/phase23/installed-matrix/phase23-installed-20260718-11/installed-scenario-matrix.json`
- `artifacts/product/phase23/hardware-matrix/phase23-hardware-20260718-06/installed-hardware-matrix.json`
