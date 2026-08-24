# Handoff 0156: Phase 21 physical qualification kit

**Date:** 2026-07-17  
**Plan step:** Phase 21.7  
**Status:** In progress; qualification tooling complete, physical run pending  
**Previous handoff:** `0155-production-remote-loss-recovery.md`

## Objective

Turn the Phase 21.7 two-physical-machine exit gate into an exact, fail-closed,
installed-code qualification procedure without substituting localhost, a VM,
container, namespace, or second prefix for the required host boundary.

## Scope completed

- Added strict content-free `PhysicalHostEvidence` and its public schema.
- Added an installed-code host probe that captures hashed machine, physical
  hardware, hostname, CPU, block, and non-loopback-network identities plus
  release, component, health, kernel, architecture, memory, and virtualization
  facts.
- Made the probe reject unhealthy installations, virtualization, unknown
  physical status, absent hardware anchors, loopback-only networking, and
  incomplete signed releases.
- Added a fail-closed report validator requiring distinct physical machines,
  one exact signed seven-component release, remote success, peer-loss recovery,
  content-free state observations, healthy diagnosis, and complete removal.
- Documented the portable signed build, installation, installed probing, manual
  pairing, physical-network success, loss recovery, final report, and removal
  procedure.
- Confirmed the current workstation reports no detected virtualization and has
  non-loopback LAN connectivity, so it is eligible for the requester role.
- Fixed a randomized Console/Core integration defect discovered by the complete
  validation run: Console session IDs now carry an alphanumeric prefix and
  cannot violate Core identity syntax when their random portion starts `_` or
  `-`. A deterministic regression forces that case.

## Explicitly not completed

- No second physical Linux host has been provided or qualified.
- No cross-host signed installation, pairing, remote-success task, peer-loss
  recovery task, dual-host inspection, or dual-host removal report exists.
- Phase 21.7 therefore remains `[~]`, and Phase 22 has not begun.

## Principal files

| Path | Purpose |
|---|---|
| `src/fam_os/fabric/physical_qualification.py` | Physical-host evidence contract |
| `tools/phase21_physical_exit/host_probe.py` | Installed physical-host probe |
| `tools/phase21_physical_exit/validation.py` | Fail-closed two-host report gate |
| `docs/operations/PHASE21_PHYSICAL_QUALIFICATION.md` | Exact cross-host procedure |
| `schemas/v1alpha1/fam.fabric.physical-host-evidence.schema.json` | Public wire contract |
| `tests/unit/test_physical_fabric_qualification.py` | Contract and report rejection coverage |
| `src/fam_os/console/sessions.py` | Core-compatible Console session identity generation |
| `tests/unit/test_console_sessions.py` | Leading-symbol session regression |

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check
.verification-venv/bin/ruff check src tests tools
.verification-venv/bin/mypy src/fam_os/fabric/physical_qualification.py src/fam_os/console/sessions.py
git diff --check
```

Current full-suite result: 1,055 tests pass with two declared hardware or
environment skips. The catalog contains 241 generated schemas. Source hygiene
validation is recorded after this handoff update.

## Next step

Provide a second physical Linux machine reachable over a non-loopback network,
with Ollama and downloaded `gemma4:26b`. Follow
`docs/operations/PHASE21_PHYSICAL_QUALIFICATION.md` from one trusted release
build through installation, pairing, success, peer loss, restart, inspection,
validation, and removal on both hosts. Only the passing cross-host artifact may
close Phase 21.7.
