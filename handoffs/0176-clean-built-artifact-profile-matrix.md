# Handoff 0176: Clean built-artifact profile matrix

**Date:** 2026-07-18  
**Plan step:** Phase 23.1–23.2  
**Status:** Complete  
**Previous handoff:** `0175-truthful-integration-coverage-refresh.md`

## Objective

Prove every declared clean dependency profile and repository suite against built
release artifacts rather than checkout imports, repairing any artifact gaps the
matrix exposed.

## Scope completed

- Reproduced 30 missing-verifier errors in a clean wheel, packaged the ten
  canonical production verifier declarations/bindings, and added exact-copy and
  wheel-fallback regressions.
- Reproduced the remaining document-index failure, traced it through runtime
  catalog composition to the missing embedding tier, and packaged the canonical
  model catalog behind signed/source precedence.
- Added a split Phase 23 matrix package for artifact build, immutable profiles,
  clean environments, unittest execution, declared skips, VS Code artifact
  lifecycle, evidence, settings, and orchestration, plus a thin CLI.
- Corrected hardware discovery to execute `*_smoke.py` without importing the two
  frozen Phase 1 parent-prototype parity comparators.
- Passed one consolidated Base, Verification, Mathematics, Media, Hardware,
  Training, and VS Code matrix from one wheel.
- Kept the installed owner service active and verified Console HTTP 200 after
  the matrix.

## Explicitly not completed

- No hardware smoke skip is counted as physical execution; Phase 23.4 remains
  open.
- The clean wheel/VSIX matrix does not satisfy installed scenarios, 24-hour
  soak, Console live-authority proof, independent human review, or the final
  signed install/update/rollback/recovery/removal gate.
- Phase 21.7 still requires a second physical Linux host.

## Architecture and decisions

ADR 0151 makes wheel-only configuration self-contained while preserving signed
release authority. It also defines artifact-origin proof and separates clean
profiles from installed, physical, soak, and human-review runners so no god
script controls the final release gate.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/resources/` | Packaged verifier, binding, identity, and runtime catalog defaults |
| `src/fam_os/product/composition/catalog_unit.py` | Signed/source/package catalog precedence |
| `pyproject.toml` | Package runtime/verifier resources and clean extras |
| `tools/phase23_release_matrix/` | Small clean-matrix implementation modules |
| `tools/run_phase23_release_matrix.py` | Thin user-facing matrix CLI |
| `tests/unit/test_packaged_runtime_catalog.py` | Catalog sync and wheel fallback regressions |
| `tests/unit/test_packaged_verifier_configuration.py` | Verifier sync and wheel fallback regressions |
| `tests/unit/test_phase23_release_matrix.py` | Profile, environment, skip, and aggregate regressions |
| `docs/operations/TEST_PROFILES.md` | Artifact-bound commands and evidence semantics |
| `configs/integration/coverage.json` | Clean-matrix maturity without installed overclaim |

## Public interfaces

```bash
.verification-venv/bin/python tools/run_phase23_release_matrix.py \
  [--profile PROFILE] [--dependency-wheelhouse PATH] \
  [--run-id ID] [--output-root PATH]
```

Omitting `--profile` selects the seven Master Plan-required profiles. The
machine-readable evidence contract is `fam.release.profile-matrix/v1alpha1`.

## Validation

```bash
.verification-venv/bin/python tools/run_phase23_release_matrix.py \
  --run-id phase23-required-20260718-01 \
  --output-root artifacts/product/phase23/profile-matrix/phase23-required-20260718-01
```

Result: passed one wheel SHA-256
`a7a8410f37d9e8a604d69094b054a98acfb31374b699a7e92717feb1e6229f2c`.
All seven profiles ran 1,257 standard tests. Base, Verification, Mathematics,
Hardware, Training, and VS Code each recorded three declared skips; Media
recorded two. Hardware also discovered 11 opt-in live smoke skips. The VS Code
profile compiled and tested the connector and installed/listed/removed VSIX
SHA-256 `c087923a1a0c079efd4cff241aeb6b5c070758566aabc747c67cd6eb0110acaa`.

## Evidence and artifacts

- `artifacts/product/phase23/profile-matrix/phase23-required-20260718-01/profile-matrix.json`
- `docs/decisions/0151-built-wheel-is-self-contained-and-profile-qualified.md`
- Per-profile install, suite, connector, and VS Code logs under the artifact root

## Known limitations and risks

- The consolidated run used pip-index dependency resolution and records exact
  resolved versions; the final signed release lifecycle must use its complete
  wheelhouse and prove offline installation separately.
- The source revision was dirty, so the wheel digest—not Git revision alone—is
  the authoritative artifact identity.
- Clean profile success is acceptance evidence, not installed operational
  evidence.

## Operational notes

Profile venvs were temporary and removed automatically. The generated wheel,
VSIX, logs, and content-free evidence remain under `artifacts/product/phase23/`.
The existing `fam-os-current.service` was not replaced and remained active on
`127.0.0.1:8765`.

## Recommended next entry point

Implement Phase 23.3 as a separate installed-release scenario matrix. Reuse the
signed bundle installer and existing Phase 18–22 scenario primitives, but keep
local, application, memory, escalation, remote, media, and Factory evidence as
separate modules feeding one aggregate installed candidate report.
