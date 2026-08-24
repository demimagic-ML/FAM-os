# Handoff 0180: Phase 23 lifecycle diagnosis and tool import correction

**Date:** 2026-07-18  
**Plan step:** Phase 23.8 readiness and whole-suite audit  
**Status:** Source and independent lifecycle steps complete; final gate remains open  
**Previous handoff:** `0179-installed-verifier-host-policy-and-total-removal.md`

## Objective

Continue the whole-Master-Plan audit from the first broad-suite and Phase 23.8
preflight failures, correct real implementation defects, and preserve the
remaining host prerequisite without weakening it.

## Scope completed

- Normalized Phase 18–23 qualification tools under the canonical `tools.*`
  package identity, eliminating discovery behavior that depended on launch
  path or `PYTHONPATH`.
- Added an architecture regression forbidding legacy top-level `phaseNN_*`
  imports in qualification tools.
- Replaced filesystem-glob installation diagnosis with a versioned expected
  path-and-digest ledger.
- Added missing, tampered, legacy, unsafe-path, repair, and lifecycle coverage.
- Made the independent sandbox probe non-fatal to later lifecycle evidence;
  one failed required event still makes the complete run fail.
- Preserved structured unhealthy host-security evidence instead of aborting
  before its receipt could be recorded.

## Explicitly not completed

- The dedicated `fam-os-userns` AppArmor profile is not loaded; sudo requires
  an administrator password.
- Phase 23.5 has not restarted its 24-hour clock.
- Phase 23.8 is not complete because its sandbox event fails and the final run
  must use the exact post-soak signed candidate and trust key.
- Phase 21.7 and the independent-human Phase 23.7 gate remain unchanged.

## Architecture and decisions

ADR 0157 makes the owner-private installation marker the expected stable-file
ledger. It is deliberately distinct from the signed active release manifest:
the release manifest protects shipped components, while the marker binds
generated launchers, generated units, and retained public trust keys.

Qualification tools are now imported as one repository package. Operational
commands use `python -m tools.run_phase...`; production runtime imports are
unchanged.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/installation_marker.py` | Versioned expected-file ledger and health checks |
| `src/fam_os/product/bundle_installation.py` | Diagnose and receipt from the ledger; write it after lifecycle changes |
| `tools/phase23_lifecycle/` | Retain sandbox failure and continue independent removal evidence |
| `tools/run_phase18_*.py` through `tools/run_phase23_*.py` | Canonical qualification package imports |
| `tests/architecture/test_qualification_tool_import_boundary.py` | Import-identity regression |
| `tests/unit/test_installation_marker.py` | Missing, digest, legacy, and path safety regression |
| `docs/operations/ATOMIC_UPDATES.md` | Current repair and diagnosis semantics |

## Public interfaces

- Persistent marker contract:
  `fam.product.signed-installation-marker/v1alpha2`.
- New diagnosis codes include `managed_file_missing:<relative-path>`,
  `managed_file_digest_mismatch:<relative-path>`,
  `installation_marker_upgrade_required`,
  `installation_marker_invalid`, and
  `installation_marker_release_mismatch`.
- Qualification runners are canonically launched with
  `python -m tools.run_phase23_<name>`.

## Validation

```bash
.verification-venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Result: 1,350 tests passed with two declared skips.

```bash
.verification-venv/bin/ruff check tools tests/architecture/test_qualification_tool_import_boundary.py
MYPYPATH=src .verification-venv/bin/mypy --strict \
  src/fam_os/product/installation_marker.py \
  src/fam_os/product/bundle_installation.py \
  tools/phase23_lifecycle tools/run_phase23_lifecycle.py
```

Result: Ruff passed; strict Mypy passed the corrected product and lifecycle
boundaries. A deliberately broader strict experiment exposed pre-existing type
debt in older evidence drivers and is not represented as a passing gate.

The exact verified-action/undo integration test passed 12 consecutive runs.
The three Phase 23 qualification test modules that previously failed discovery
now pass with 26 tests.

## Evidence and artifacts

- `artifacts/product/phase23/lifecycle/phase23-lifecycle-preflight-20260718-01/`
  retains the original false-health failure.
- `artifacts/product/phase23/lifecycle/phase23-lifecycle-preflight-20260718-04/installed-lifecycle.json`
  proves install, update, rollback, damage diagnosis, repair, connector install,
  service HTTP 200, and total removal; only the required sandbox event fails.
- ADR 0157 records the persistent marker decision.

## Known limitations and risks

- The marker is owner-scoped integrity state. A process that has already
  compromised the same Unix account can rewrite both a stable file and marker;
  this is outside the stated trust boundary.
- Final installed sandbox, soak, and lifecycle evidence cannot pass until an
  administrator loads the dedicated AppArmor profile.
- Older qualification drivers are not all strict-Mypy clean even though the
  runtime, declared gates, and corrected Phase 23.8 boundary pass typing.

## Operational notes

The owner service remained active on `127.0.0.1:8765`; the candidate used port
18765 and was completely removed. `fam-os.service` and `fam-ollama.service` are
inactive after the preflight. Follow
`docs/operations/APPARMOR_VERIFIER_PROFILE.md` before another qualification.

## Recommended next entry point

Load `packaging/systemd/fam-os-userns` as documented, run a new complete
Phase 23.8 preflight, then restart the Phase 23.5 24-hour candidate from zero.

