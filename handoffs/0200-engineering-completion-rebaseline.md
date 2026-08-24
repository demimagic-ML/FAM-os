# Handoff 0200: Engineering completion rebaseline

**Date:** 2026-07-19  
**Plan step:** Phases 27.11--27.16, 29.7--29.8, and 30.1/30.5--30.9  
**Status:** Partial  
**Previous handoff:** `0199-installed-engineering-security-qualification-partial.md`

## Objective

Audit the complete persistent goal against the actual engineering public
surface, installed composition, canonical coverage, and Phase 31 prerequisites
so omitted powers cannot be hidden behind narrower checked milestones.

## Scope completed

- Confirmed the verifier host policy still fails closed and requires owner
  administrator authentication.
- Confirmed canonical coverage records the engineering authorities and
  candidate workspace as component-tested and not production-reachable.
- Confirmed the master loop is a persistent state contract, not a product
  composition that invokes the engineering services.
- Added explicit plan work for runtime diagnosis, database engineering,
  environments, deployment/IaC, releases, secret rotation, complete Git,
  multi-repository delivery, documentation/generated content, incidents,
  independent review, and installed product composition.
- Reopened Phase 30.1 and 30.5 to match their production-facing wording.
- Added the first Phase 27.11 strict runtime-diagnostics contract and schema
  slice with cross-contract bounds and baseline validation.
- Reused signed tool-recipe admission with eight exact diagnostic purposes;
  kind, digest, environment, and network substitutions fail closed.

## Explicitly not completed

- The remaining newly explicit contracts, adapters, composition, schemas, and
  tests, including real diagnostic adapters and release-owned recipe specs.
- AppArmor profile installation, final physical aggregate, 24-hour soak,
  independent human security review, and operational coverage promotion.

## Architecture and decisions

The status correction applies accepted ADR 0111:
component and acceptance evidence cannot imply production reachability. The
existing narrow component evidence remains valid and append-only.

ADR 0175 keeps runtime diagnostics in unprivileged candidate sandboxes, binds
them to signed recipes and exact baselines, and forbids unsanitized or
secret-bearing diagnostic artifacts from becoming evidence.

## Files changed

| Path | Purpose |
|---|---|
| `MASTER_PLANv2.md` | Rebaseline completion state and add omitted requirements |
| `docs/operations/ENGINEERING_COMPLETION_AUDIT_20260719.md` | Requirement-to-evidence audit and corrective order |
| `handoffs/0200-engineering-completion-rebaseline.md` | Historical record of the status correction |
| `docs/decisions/0175-runtime-diagnostics-are-signed-bounded-and-sanitized.md` | Runtime-diagnostics security boundary |
| `src/fam_os/core/engineering/diagnostics.py` | Runtime diagnostic contracts and validation |
| `src/fam_os/core/engineering/diagnostic_policy.py` | Exact signed recipe admission policy |
| `src/fam_os/core/engineering/execution.py` | Signed diagnostic recipe-purpose vocabulary |
| `src/fam_os/core/engineering/__init__.py` | Public diagnostic exports |
| `src/fam_os/schemas/catalog.py` | Diagnostic schema registration |
| `schemas/v1alpha1/fam.core.runtime-diagnostic-request.schema.json` | Strict request schema |
| `schemas/v1alpha1/fam.core.runtime-diagnostic-receipt.schema.json` | Strict receipt schema |
| `tests/contract/schema_diagnostics_fixtures.py` | Representative schema values |
| `tests/contract/test_schema_roundtrip.py` | Diagnostic schema roundtrip coverage |
| `tests/contract/test_schema_compatibility.py` | Strict-version rejection coverage |
| `tests/unit/test_runtime_diagnostics.py` | Diagnostic policy tests |

## Public interfaces

New numbered plan requirements were added and Phase 30.1/30.5 status changed
from checked to open. New public interfaces are `RuntimeDiagnosticKind`,
`DiagnosticArtifactKind`, `RuntimeDiagnosticStatus`,
`RuntimeDiagnosticLimits`, `RuntimeDiagnosticRequest`,
`RuntimeDiagnosticArtifact`, `RuntimeDiagnosticReceipt`, and
`validate_runtime_diagnostic_receipt`, `RuntimeDiagnosticRecipePolicy`, and
eight `ToolRecipePurpose` values, plus two `fam.core` schema roots.

## Validation

```bash
larry search "runtime debugging stack traces crash dumps tracing profiling race detection performance regression engineering"
larry search "database schemas migrations fixtures backups restores transactional testing rollback engineering"
larry search "service orchestration browser containers local clusters kubernetes infrastructure deployment IaC engineering"
larry search "git fetch merge rebase conflict tags releases artifact signing registry release rollback multi repository generated code"
rg -n 'MasterEngineeringLoop|EngineeringGrantLedger|CandidateWorkspaceService|GitPublicationService|DesignAssetService|EngineeringDependencyService' src/fam_os --glob '!core/engineering/**' --glob '!adapters/**'
systemd-run --user --wait --collect -p AppArmorProfile=fam-os-userns -- /usr/bin/true
sudo -n true
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.unit.test_runtime_diagnostics tests.contract.test_schema_roundtrip tests.contract.test_schema_compatibility -v
PYTHONPATH=src:. .verification-venv/bin/python tools/render_contract_schemas.py --check --output schemas
PYTHONPATH=src:. .verification-venv/bin/python -m unittest tests.architecture.test_product_composition_boundary tests.architecture.test_qualification_tool_import_boundary -v
PYTHONPATH=src:. .verification-venv/bin/python -m compileall -q src tests/contract tests/unit/test_runtime_diagnostics.py
git diff --check
```

Result: no installed product-composition references were found for the audited
engineering services. The AppArmor probe exited 231 and noninteractive sudo
exited 1 with `a password is required`. The final diagnostics/schema suite
passed 31 tests, the architecture boundary suite passed 3 tests, schema
rendering validated 347 artifacts, compileall passed, and `git diff --check`
reported no errors.

The first signed-recipe test failed because its request attempted to add
`PYTHONPATH` to a recipe that allowed no environment keys. The fixture was
corrected to the signed empty environment; policy was not weakened.

## Evidence and artifacts

- `docs/operations/ENGINEERING_COMPLETION_AUDIT_20260719.md`
- `configs/integration/coverage.json`
- `docs/decisions/0111-final-integration-requires-production-reachability.md`
- `artifacts/engineering/phase31/hardware-matrix/phase31-engineering-hardware-20260718-04/installed-hardware-matrix.json`

## Known limitations and risks

- Prior Phase 24--30 prose can still be misread as whole-phase completion; the
  audit correction and canonical coverage must be read together.
- The Larry map predates the newest untracked engineering files, so Larry was
  used first and direct source search filled the documented gap.
- Phase 31 cannot pass until owner-authenticated host policy and independent
  human review are available.

## Operational notes

Do not start the soak until the AppArmor prerequisite and clean physical
preflight pass. Do not promote engineering coverage from component or short
installed evidence.

## Recommended next entry point

Start Phase 27.11 by defining bounded runtime-diagnostics contracts and strict
schemas, then add signed recipes, real adapters, and positive and hostile
fixtures without granting host-process attach authority.
