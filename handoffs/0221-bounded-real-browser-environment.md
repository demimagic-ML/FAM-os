# Handoff 0221: Bounded real browser environment

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 real browser backend  
**Status:** Partial  
**Previous handoff:** `0220-installed-owner-process-restart-chain.md`

## Objective

Run and control a real browser through a signed, content-bound recipe without
granting raw browser, host-toolchain, or DevTools authority.

## Scope completed

- Routed homogeneous browser plans to the process backend.
- Verified root-owned browser toolchain trees against signed recipe digests and
  mounted matching content read-only inside Bubblewrap.
- Supported one embedded declared-port token in an otherwise fixed signed arg.
- Started real headless Google Chrome in a bounded user systemd scope with an
  ephemeral profile and loopback-only DevTools.
- Added a bounded DevTools client for return-by-value evaluation and strict,
  size-bounded PNG screenshots.
- Proved malformed endpoints, masked/oversized frames, and invalid screenshots
  fail closed.
- Proved health, real control, cleanup, and zero surviving process scopes.
- Added browser positive and negative tests to fresh-wheel, no-source-path
  qualification across both declared profile labels.

## Explicitly not completed

- A portable release-installed Chrome/toolchain package and production browser recipe.
- Browser allowlisted egress, downloads, retained artifacts, or user-visible
  Console/Shell browser-control operations.
- Mixed local clusters or independently enforced/physical profile evidence.

## Architecture and decisions

ADR 0188 binds host browser content to the signed recipe and keeps DevTools
behind an operation-shaped bounded adapter. It explicitly forbids treating a
host browser path or raw CDP socket as authority. The generic release remains
portable by declining to embed this host's Chrome digest automatically.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/integration/process_environment.py` | Browser launch, fixed embedded port, and read-only system mounts |
| `src/fam_os/adapters/integration/process_toolchains.py` | Root-owned content-bound toolchain mounts |
| `src/fam_os/adapters/integration/devtools_client.py` | Bounded loopback DevTools operations |
| `src/fam_os/adapters/integration/environment_router.py` | Browser backend selection |
| `tests/unit/test_bounded_devtools_client.py` | Fail-closed protocol fixtures |
| `tests/integration/test_real_browser_integration_environment.py` | Real Chrome control and cleanup |
| `tools/run_phase27_integration_environment_qualification.py` | Installed browser scenarios |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt5.json` | Superseding installed evidence |

## Public interfaces

- `BoundedDevToolsClient.targets()`
- `BoundedDevToolsClient.evaluate(expression)`
- `BoundedDevToolsClient.screenshot_png()`
- Browser services are accepted by `IntegrationEnvironmentRouter` when every
  service in the plan belongs to the process-backed kind set.

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_bounded_devtools_client \
  tests.integration.test_real_browser_integration_environment -v

.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt5.json \
  --repository . \
  --builder-python .verification-venv/bin/python
```

Result: focused source validation passed 5 tests in 4.502 seconds. Installed
attempt 5 passed in 37.157232 seconds; each same-host declared profile label
passed 24 tests with no repository source path. Wheel SHA-256:
`2a9841bc6ae16d1371af10d8743d456d14ca04f591fd4672c8c3c787728f5f86`.
Signer public-key SHA-256:
`3ed685bf4b2b0c130d095e6958d2c4ebfc90bee63ac236152e9767806bc40bbc`.

Failed Firefox/Snap and initial Chrome port-shape trials terminated safely and
left no `fam-int-*` scope.

## Evidence and artifacts

- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt5.json`
- `docs/decisions/0188-browser-environments-use-content-bound-toolchains-and-bounded-devtools.md`
- Measured host: x86-64, 24 logical CPUs, 65,447,104 KiB RAM, kernel
  6.17.0-35-generic.

## Known limitations and risks

- Both profile labels ran on one host without independently enforced ceilings.
- The qualification signer is ephemeral, not the production release trust root.
- Hashing the 403 MiB Chrome tree on each launch is correct but expensive.
- Chrome currently uses `--no-sandbox` because Bubblewrap is the outer sandbox;
  the installed production profile must preserve that outer boundary.

## Operational notes

No FAM browser process scope remained after either source or installed
qualification. No browser profile or screenshot artifact was retained.

## Recommended next entry point

Add a signed installed browser-toolchain package/catalog entry and compose it
into product routing only when its release trust and exact content digest pass.
Then expose capability-shaped owner controls without exposing raw DevTools.
