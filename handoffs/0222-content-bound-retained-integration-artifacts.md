# Handoff 0222: Content-bound retained integration artifacts

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 retained artifact evidence  
**Status:** Partial  
**Previous handoff:** `0221-bounded-real-browser-environment.md`

## Objective

Make declared integration outputs survive cleanup as exact bounded evidence
without adding general filesystem or artifact-store authority.

## Scope completed

- Added race-aware, no-follow, candidate-confined regular-file hashing.
- Enforced the cumulative changed-byte budget and excluded internal state.
- Captured artifacts only after exact process/container teardown.
- Added artifact evidence to cleanup and restart reconciliation receipts.
- Required retained Docker volume paths to be declared plan artifacts.
- Proved a real sandboxed API creates an output whose expected SHA-256 appears
  in its cleanup receipt.
- Added positive and deliberately failing fixtures to installed qualification.

## Explicitly not completed

- A durable export/store, downloads, retention duration, or garbage collection.
- Mixed-backend orchestration, allowlisted egress, or process secret injection.
- Independent physical profile qualification.

## Architecture and decisions

ADR 0189 defines retention as content evidence over the existing candidate,
not a copy or publication action. This preserves the distinction between
verification evidence and filesystem/publication authority.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/integration/retained_artifacts.py` | Bounded artifact capture |
| `src/fam_os/adapters/integration/process_environment.py` | Process cleanup/reconcile evidence |
| `src/fam_os/adapters/integration/docker_environment.py` | Docker cleanup/reconcile evidence |
| `tests/unit/test_integration_retained_artifacts.py` | Escape, internal, missing, and budget failures |
| `tests/integration/test_process_api_integration_environment.py` | Real generated artifact proof |
| `tools/run_phase27_integration_environment_qualification.py` | Installed artifact matrix |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt6.json` | Superseding evidence |

## Public interfaces

No schema changed. Concrete adapters now populate the existing
`IntegrationEnvironmentReceipt.retained_artifacts` contract.

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_integration_retained_artifacts \
  tests.unit.test_process_integration_environment \
  tests.unit.test_docker_integration_environment -v

PYTHONPATH=src python3 -m unittest \
  tests.integration.test_process_api_integration_environment -v

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt6.json \
  --repository . --builder-python .verification-venv/bin/python

PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t . -v
```

Result: adapter/unit validation passed 9 tests; the real API passed in 4.211
seconds. Installed attempt 6 passed in 37.165102 seconds with 26 tests per
same-host profile label. Wheel SHA-256:
`697665bf91e72d03ded7cf8230efceb3a29c472d6fdf8bbe452c65a6caa97909`.
Signer key SHA-256:
`9acdfe5f61120aeda71fb20e5f31be01874f0da8f6db1baed7a0fc4d489d99b3`.
The architecture boundary suite passed all 41 tests in 0.708 seconds.
A combined integration-environment baseline passed all 45 focused tests in
16.288 seconds.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt6.json`
- `docs/decisions/0189-retained-integration-artifacts-are-post-stop-content-evidence.md`

## Known limitations and risks

- Receipt evidence does not preserve bytes if later candidate work changes or
  deletes the file.
- Both profile labels ran on one physical host without distinct ceilings.
- Qualification uses an ephemeral signer.

## Operational notes

No `fam-int-*` scope remained after qualification.

## Recommended next entry point

Design mixed-backend orchestration around backend service-level primitives and
one aggregate journal; do not split whole-environment plans at the router.
