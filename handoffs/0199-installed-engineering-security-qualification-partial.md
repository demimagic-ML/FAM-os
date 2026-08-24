# Handoff 0199: Installed engineering security qualification partial

**Date:** 2026-07-18  
**Plan step:** Phase 31.1 and 31.3  
**Status:** Partial  
**Previous handoff:** `0198-bounded-master-engineering-loop.md`

## Objective

Prove adversarial behavior and the complete new engineering fabric from a
freshly installed signed artifact without overstating short or constrained runs.

## Scope completed

- Added a complete sixteen-category adversarial coverage ledger and direct
  security tests for filesystem links, archives, network, process/output
  pressure, media, dependency, Git, stale authority, and replay boundaries.
- Changed subprocess capture to terminate and fail closed on output overflow.
- Added fail-closed qualification, independent-review, and 24-hour-soak
  contracts; a pass cannot omit or shorten those gates.
- Built, Ed25519-signed, verified, installed, and imported a new wheel in a fresh
  venv; all twelve language fixtures and 89 installed tests pass.
- Ran physical installed hardware qualification. Both named profile bodies pass
  and owner service/removal postconditions pass.
- Repaired stale production verifier-tree digests and a code-only `implement`
  intent misclassification found by the physical run.

## Explicitly not completed

- Phase 31.2: the aggregate physical matrix still fails because the dedicated
  `fam-os-userns` AppArmor profile is not loaded; dependency profiles also need
  their final installed aggregate.
- Phase 31.4: the 24-hour soak has not started.
- Phase 31.5: an independent human has not completed and signed the review.
- Phase 31.6: installed coverage remains unchanged until all gates pass.

## Architecture and decisions

ADR 0174 introduces an aggregate that rejects false operational proof. The
implementing agent cannot satisfy independent review, and a development-duration
soak cannot satisfy the 86,400-second minimum.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/security_qualification.py` | Fail-closed review/soak/aggregate contracts |
| `src/fam_os/core/engineering/security_coverage.py` | Exact adversarial test ledger |
| `tests/security/test_engineering_adversarial.py` | Direct hostile fixtures |
| `tools/run_phase31_signed_engineering.py` | Built signed installed matrix |
| `tools/run_phase31_engineering_soak.py` | Resumable minimum-duration soak runner |
| `docs/security/ENGINEERING_SECURITY_REVIEW_TEMPLATE.md` | Independent review template |
| `docs/operations/ENGINEERING_PHASE31_PREREQUISITES.md` | Owner prerequisite procedure |

## Public interfaces

`EngineeringSecurityReview`, `EngineeringPressureSoakReport`,
`InstalledEngineeringQualification`, `EngineeringQualificationStatus`, and
`ENGINEERING_ADVERSARIAL_TESTS`.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python tools/run_phase31_signed_engineering.py --output artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt3.json
PYTHONPATH=src:. .verification-venv/bin/python tools/run_phase23_hardware_matrix.py --run-id phase31-engineering-hardware-20260718-04 --output-root artifacts/engineering/phase31/hardware-matrix/phase31-engineering-hardware-20260718-04 --quiesce-owner-models
```

Result: signed installed engineering evidence passes in 87.57 seconds with 89
installed tests. Both physical profile bodies pass. The aggregate hardware
runner remains failed because every strong Python verification reports
`Required AppArmor verifier profile could not be applied: fam-os-userns`.
Candidate removal and owner-service preservation pass.

## Evidence and artifacts

- Passing installed suite: `artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt3.json`
- Latest physical evidence: `artifacts/engineering/phase31/hardware-matrix/phase31-engineering-hardware-20260718-04/installed-hardware-matrix.json`
- Preserved earlier physical failures: runs `-01`, `-02`, and `-03`
- `docs/decisions/0174-engineering-operational-proof-requires-soak-and-independent-review.md`

## Known limitations and risks

- `fam-os-userns` requires an owner-authenticated host policy change; no model or
  unprivileged Core process may load it.
- A 24-hour run can still uncover cleanup or pressure defects; no short evidence
  is a substitute.
- Independent review can identify blocking findings that require another cycle.

## Operational notes

Follow `docs/operations/ENGINEERING_PHASE31_PREREQUISITES.md`. Do not start the
soak clock until the AppArmor profile and clean physical preflight pass.

## Recommended next entry point

The owner loads `fam-os-userns`; rerun the physical matrix. Then create a stable
signed installed soak environment, run the 24-hour soak, obtain the independent
review, and only then update installed coverage.
