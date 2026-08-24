# Handoff 0194: Signed polyglot execution foundation

**Date:** 2026-07-18  
**Plan step:** Phase 27.1, 27.4, and 27.10  
**Status:** Complete  
**Previous handoff:** `0193-transactional-candidate-workspaces.md`

## Objective

Make signed typed recipes the ordinary engineering execution path, keep raw
shell exceptional and exact, prove real candidate containment, and separate
opaque, redacted, and directly disclosed secret use.

## Scope completed

- Added twelve strict execution, dependency, host-admin, and secret document
  roots plus polyglot recipe-matrix completeness policy.
- Added Ed25519 recipe admission and immutable coordinates.
- Added exact single-use raw-shell authorization and execution.
- Added generalized Bubblewrap candidate execution with systemd cgroups,
  rlimits, no network, no host home, no inherited credentials, disabled Git
  configuration/hooks, bounded output, and digest-checked toolchain mounts.
- Added positive/negative containment qualification and real source fixtures
  for Python, JavaScript, TypeScript, Rust, Go, Java, Kotlin, C, C++, shell,
  HTML, and CSS.
- Added dependency admission/receipt policy and Core resolver port, external
  host-admin broker gate/service, and separate opaque/redacted/direct secret
  service with single-use consumption.

## Explicitly not completed

- Phase 27.2 remains open because the passing matrix is source qualification,
  not a signed installed release.
- Phase 27.3 and 27.5–27.9 remain open until production recipe definitions,
  real isolated dependency adapters, signed verifier packages, and installed
  external administration/global-install broker evidence exist.

## Architecture and decisions

ADR 0170 records signed recipe admission, exact raw shell, candidate sandbox,
external privilege, isolated dependency, and three-level secret boundaries.
Core stays unprivileged and concrete toolchains, processes, registries, and OS
administration remain behind adapters or external broker ports.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/execution.py` | Recipe, sandbox, shell, receipt, qualification contracts |
| `src/fam_os/core/engineering/execution_policy.py` | Signature catalog and raw-shell gate |
| `src/fam_os/core/engineering/recipe_matrix.py` | Required ecosystem/purpose coverage |
| `src/fam_os/core/engineering/qualification.py` | Positive/negative fail-closed qualification |
| `src/fam_os/core/engineering/dependencies.py` | Dependency and SBOM contracts |
| `src/fam_os/core/engineering/dependency_policy.py` | Registry, budget, license, vulnerability policy |
| `src/fam_os/core/engineering/dependency_service.py` | Resolver orchestration port |
| `src/fam_os/core/engineering/privileged.py` | Host and secret contracts |
| `src/fam_os/core/engineering/privileged_policy.py` | External broker and secret gates |
| `src/fam_os/core/engineering/host_admin_service.py` | Authenticated broker orchestration |
| `src/fam_os/core/engineering/secret_service.py` | Tiered single-use secret service |
| `src/fam_os/adapters/bubblewrap/engineering.py` | General candidate sandbox |
| `src/fam_os/adapters/linux/raw_shell.py` | Exact raw-shell execution adapter |
| `src/fam_os/adapters/crypto/engineering_recipes.py` | Ed25519 verification adapter |
| `tools/verifiers/web_quality.py` | Deterministic HTML/CSS verifier |
| `tests/unit/test_engineering_execution.py` | Authority and receipt tests |
| `tests/integration/test_polyglot_engineering_sandbox.py` | Real twelve-ecosystem matrix |
| `tools/run_phase27_polyglot_matrix.py` | Raw evidence runner |

## Public interfaces

`SignedToolRecipe`, `ToolchainMount`, `EngineeringSandboxProfile`,
`RawShellAuthorization`, `EngineeringToolReceipt`, `LanguageToolQualification`,
`PolyglotRecipeMatrix`, dependency request/receipt/SBOM contracts,
host-admin changeset/receipt, secret authorization/receipt, and their Core
admission services.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_engineering_execution tests.unit.test_web_quality_verifier tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility tests.contract.test_cross_contract_references -v
PYTHONPATH=src:. python3 -m unittest tests.integration.test_polyglot_engineering_sandbox -v
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
git diff --check
```

Result: 44 focused unit/contract tests pass; the real twelve-ecosystem sandbox
matrix passes in 37.4 seconds interactively and 38.8 seconds in the evidence
runner; 333 schemas validate; diff whitespace validation passes.

## Evidence and artifacts

- Passing: `artifacts/engineering/phase27/polyglot-source-qualification-20260718-attempt2.json`
- Preserved failed environment attempt: `artifacts/engineering/phase27/polyglot-source-qualification-20260718.json`
- ADR: `docs/decisions/0170-engineering-execution-uses-signed-recipes-and-external-privilege.md`

## Known limitations and risks

- Toolchain tree hashing is intentionally complete and adds qualification time.
- The source test uses existing host toolchain artifacts exposed at narrow
  signed `/opt/fam/toolchains` mounts; the installed release must package or
  explicitly inventory equivalent toolchains.
- Network allowlist proxy and concrete dependency ecosystem adapters remain
  open; networked recipe execution currently fails closed.
- Host administration is an authenticated external broker contract and fake,
  not yet an installed privileged service.

## Operational notes

The first evidence-run attempt intentionally remains preserved: it omitted the
systemd user-bus control environment and failed before containment. The runner
now passes only `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` to the systemd
wrapper; Bubblewrap still clears them from the candidate.

## Recommended next entry point

Continue Phase 27.3 and 27.5–27.9. Start with production signed recipe
definitions and a network allowlist proxy-backed dependency resolver, then bind
the promoted language verifiers into the signed release catalog.
