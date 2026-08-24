# Handoff 0259: Signed installed natural service composition

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 and installed portions of 30.1/30.5  
**Status:** Partial (`installed_component_tested`; host production verifier unavailable)  
**Previous handoff:** `0258-versioned-natural-service-declaration.md`

## Objective

Prove that the versioned natural API/static service graph from ADR 0223 works
from one freshly built, signed, isolated installation rather than only from the
source checkout.

## Scope completed

- Built a fresh `fam_os-0.1.0` wheel and complete seven-component signed bundle
  as release `phase30-natural-integration-20260719-1`.
- Installed that bundle into a new isolated prefix and verified the signed
  installation marker, managed-file identities, release identity, and empty
  installation issue set.
- Added a fail-fast installed-package qualification runner that rejects checkout
  import leakage before loading the installed recipe catalog and test suite.
- Loaded all 415 public schema roots and both exact signed natural-integration
  recipes from the installed release.
- Passed 100 installed-package-first unit, contract, transport, Console, natural
  lifecycle, and real two-service process tests. The real process row observed
  both API and static services healthy and cleaned them after use.
- Recorded the release, wheel, manifest, installed-module, recipe, schema, test,
  and host-security identities in one machine-readable evidence artifact.
- Diagnosed the production verifier separately. It correctly remains
  unavailable because the root-owned `fam-os-userns` AppArmor profile is not
  loaded; the evidence therefore reports component success without claiming
  product or phase completion.

## Explicitly not completed

- No live installation, service, release, or owner repository was changed.
- The production verifier did not run because its required host profile remains
  unavailable.
- Browser, container, mixed-backend, and local-cluster natural composition is
  not complete.
- Safe dynamic port reservation, explicit natural network/opaque-secret
  ceremonies, and remote-database attachment remain open.
- Both-profile qualification, the 24-hour soak, and independent human security
  review remain open.

## Architecture and decisions

No durable architecture decision changed. This handoff qualifies the contracts
and boundaries established by ADR 0223 from a signed isolated installation.
The declaration still cannot select commands, recipes, ports, network access,
secrets, volumes, artifacts, budgets, or authorities; Core maps its closed
logical roles to release-owned signed recipes.

The overall evidence remains fail-closed: `installed_component_passed` is true,
while top-level `passed` is false and status is
`installed_component_tested_host_security_blocked` until the independent host
policy exists and the production verifier can enforce it.

## Files changed

| Path | Purpose |
|---|---|
| `tools/run_phase30_natural_integration_installed.py` | Installed-package-first qualification and checkout-leakage guard |
| `artifacts/product/phase30/natural-integration-install-20260719-01/evidence.json` | Signed installed release and host-gate evidence |
| `MASTER_PLANv2.md` | Phase 27.13 and Phase 30 installed evidence update |
| `MASTER_PLAN.md` | Companion-plan evidence update |
| `MASTER_PLANv2_STATUS_AUDIT.md` | Current maturity and remaining-gap update |
| `MASTER_PLANv2_COMPLETION_PROMPT.md` | Resumable baseline update |
| `handoffs/README.md` | Handoff sequence update |

## Public interfaces

No runtime public contract or schema changed. The installed schema catalog
remains at 415 roots. The new runner is an operator/developer qualification
tool, not a runtime authority surface.

## Validation

```bash
/usr/bin/python3.12 -I tools/run_phase30_natural_integration_installed.py \
  --installed-root /tmp/fam-os-phase30-natural-integration-install-20260719-1/active \
  --repository /home/demimagic/Desktop/NewLLM/FAM_OS \
  --expected-schemas 415

/tmp/fam-os-phase30-natural-integration-install-20260719-1/bin/fam-os \
  --prefix /tmp/fam-os-phase30-natural-integration-install-20260719-1 \
  diagnose

/tmp/fam-os-phase30-natural-integration-install-20260719-1/bin/fam-os \
  --prefix /tmp/fam-os-phase30-natural-integration-install-20260719-1 \
  host-security diagnose
```

Results:

- Installed qualification: 100 tests, 0 failures, 0 errors.
- Installed identity: code loaded from
  `/tmp/fam-os-phase30-natural-integration-install-20260719-1/releases/phase30-natural-integration-20260719-1/python/fam_os/__init__.py`.
- Installed recipe coordinates:
  `integration.python.root-api@1.0.0` and
  `integration.python.static-http@1.0.0`.
- Schema count: 415.
- Installation diagnosis: healthy, no issues.
- Host-security diagnosis: exit 1, status `unavailable`, isolation `none`,
  because `fam-os-userns` could not be applied. This is the expected fail-closed
  external gate, not an installed natural-composition test failure.

Identities:

- Manifest SHA-256:
  `500fe0f54bc1a6533fb73fe4e97c0bf3690da1a5bff70ce394077ff3f49fbaa7`
- Wheel SHA-256:
  `8bf477c9f6eb77644ae34dae910a3273ce503431b45225fd45031bd9590ddb67`

## Evidence and artifacts

- `artifacts/product/phase30/natural-integration-install-20260719-01/evidence.json`
- `/tmp/fam-os-phase30-natural-integration-20260719-1/bundle/manifest.json`
- `/tmp/fam-os-phase30-natural-integration-install-20260719-1/.fam-os-signed-installation.json`

The `/tmp` paths are ephemeral operational evidence; the repository artifact
contains the durable identities and results.

## Known limitations and risks

- The API recipe still expects root `api.py`, a port argument, and `/health`.
- The declaration remains limited to two fixed templates.
- Ports are selected before process launch and retain the documented bounded
  race.
- The signed installed proof is isolated and component-scoped, not a live
  deployment or complete Phase 27.13 qualification.

## Operational notes

No live service, active release, host policy, root-owned profile, credential,
owner repository, network broker, container, or external system changed. The
isolated installation remains under `/tmp` for inspection.

## Recommended next entry point

Continue Phase 27.13 at the next authority boundary: design a separate,
resource-scoped natural proposal and owner-approval ceremony for integration
network access and opaque secret attachment. Do not add these fields to the
v1alpha1 service declaration or auto-grant separately confirmed authorities.
Start with ADRs 0188, 0191, 0196, and 0223 and the existing grant,
`IntegrationEnvironmentService`, and natural integration composition APIs.
