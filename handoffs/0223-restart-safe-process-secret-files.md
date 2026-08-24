# Handoff 0223: Restart-safe process secret files

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 process/API/browser opaque secret injection  
**Status:** Partial  
**Previous handoff:** `0222-content-bound-retained-integration-artifacts.md`

## Objective

Provide bounded file-only secret consumption for process-backed integration
services without leaking values in commands or orphaning plaintext on restart.

## Scope completed

- Added bounded file-only provider materialization and denied dangerous keys.
- Journaled relative secret-root identities before asynchronous launch.
- Added backward-compatible legacy journal normalization.
- Erased roots after cleanup, launch failure, revocation, and restart reconcile.
- Hid all candidate secret roots behind sandbox tmpfs while mounting only the
  current service's files at `/run/fam-secrets`.
- Wired the same optional provider into Docker and process product composition.
- Proved a real Bubblewrap HTTP API consumes the secret file and cannot inspect
  the candidate secret-root directory.
- Added installed-wheel positive, hostile, revocation, and restart fixtures.

## Explicitly not completed

- An authenticated encrypted product secret-reference repository/provider and
  Console/Shell provisioning, rotation, revocation, or deletion controls.
- Mixed-backend orchestration, allowlisted egress, or portable browser packaging.
- Independent physical profile evidence, soak, or human review.

## Architecture and decisions

ADR 0190 defines the plaintext lifetime, durable non-secret cleanup identity,
restart compatibility, sandbox visibility, and current same-UID trust limit.
Product remains default-deny until an owner-controlled provider is composed.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/integration/process_secrets.py` | File materialization and erasure |
| `src/fam_os/adapters/integration/process_state.py` | Restart-safe secret-root identities |
| `src/fam_os/adapters/integration/process_recipes.py` | Extracted fixed recipe expansion |
| `src/fam_os/adapters/integration/process_environment.py` | Launch, shadow, cleanup, reconcile |
| `src/fam_os/product/composition/integration_environment.py` | Shared optional provider wiring |
| `tests/unit/test_process_integration_environment.py` | Hostile, revocation, restart tests |
| `tests/unit/test_process_environment_state.py` | Journal compatibility tests |
| `tests/integration/test_process_api_integration_environment.py` | Real secret consumption/isolation |
| `tools/run_phase27_integration_environment_qualification.py` | Installed scenarios |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt7.json` | Installed evidence |

## Public interfaces

`ProcessIntegrationEnvironmentAdapter` now accepts an optional `secrets`
provider with the same `environment(secret_refs, consumer_id)` shape as Docker.
No serialized public contract changed.

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_process_integration_environment \
  tests.unit.test_process_environment_state \
  tests.integration.test_process_api_integration_environment -v

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt7.json \
  --repository . --builder-python .verification-venv/bin/python

PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t . -v

PYTHONPATH=src python3 -m unittest tests.contract.test_integration_coverage -v
```

Result: focused secret validation passed 8 tests in 1.085 seconds. The complete
environment baseline passed 50 tests in 6.955 seconds; all 41 architecture
tests passed in 0.749 seconds. Installed attempt 7 passed 33 tests per
same-host profile label in 18.280171 seconds without checkout imports. Wheel
SHA-256: `85278f66b8090c66e2749c54cb6a7996fcfb1d76b049b762d8105edcf909f84b`.
Signer-key SHA-256:
`f737ec1f13f24e6ac294332a8b2b19e3072bc570240d90d42015f7c9de344f33`.
The coverage contract passed all 8 tests in 0.409 seconds.

An initial invocation used the nonexistent legacy module
`tests.unit.test_integration_coverage` and failed import. The actual contract
suite then exposed that the existing `engineering_candidate_workspace` item
was absent from the required-subsystem set; the set now requires both that
existing item and `engineering_integration_environment`.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt7.json`
- `docs/decisions/0190-process-secrets-are-file-only-journaled-and-restart-erased.md`

## Known limitations and risks

- Product composition defaults to denial because no owner secret repository is
  installed yet.
- Same-UID host processes can inspect active mode-0600 files.
- Both profile labels ran on one host without distinct enforced ceilings.
- Qualification uses an ephemeral signer.

## Operational notes

No `fam-int-*` scope or `process-*` secret root remained after qualification.

## Recommended next entry point

Create an encrypted owner-scoped secret-reference repository, authenticated
provision/rotate/delete APIs, and an opaque environment provider that consumes
only exact grant-bound references without exposing plaintext to Core or logs.
