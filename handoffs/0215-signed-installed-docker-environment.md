# Handoff 0215: Signed installed Docker environment

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 installed qualification  
**Status:** Partial  
**Previous handoff:** `0214-optional-product-docker-composition.md`

## Objective

Prove the bounded real-container lifecycle from a signed installed artifact.

## Scope completed

- Added a dedicated build/sign/install qualifier for the real Docker scenario.
- Built an Ed25519-signed wheel, installed it into a fresh environment, and
  proved `fam_os` loaded from `site-packages`.
- Ran the digest-pinned cached PostgreSQL lifecycle under both declared profile
  scenario labels.
- Re-proved internal networking, resource bounds, signed health, file-based
  secret injection, daemon-metadata plaintext absence, restart reconciliation,
  and complete container/network cleanup from the installed package.
- Recorded the physical host identity and exact wheel/signer digests.

## Explicitly not completed

- Independently enforced profile cgroups or a second host.
- Other environment kinds, owner controls, retained artifacts, or allowlisted
  egress.
- Phase 27.13 exit gate.

## Files changed

| Path | Purpose |
|---|---|
| `tools/run_phase27_integration_environment_qualification.py` | Signed installed scenario qualifier |
| `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt1.json` | Passing installed evidence |

## Validation

```bash
.verification-venv/bin/python \
  tools/run_phase27_integration_environment_qualification.py \
  --output artifacts/engineering/phase27/integration-environment-installed-20260719-attempt1.json \
  --repository . --builder-python .verification-venv/bin/python
```

Result: passed in 7.08 seconds. Both declared profile scenarios passed from
`site-packages`. Wheel SHA-256 is
`da73450e6b025efee6d28779a0d5fe658bf2a7345735ecba88aee30d2a968398`;
signer public-key SHA-256 is
`b5e07fc5e6a30a2fe705aae3aeb47c6af72fe5444060361ab3837209b624b071`.
The measured host had 24 logical CPUs, 65,447,104 KiB RAM, x86-64, and kernel
6.17.0-35-generic. No labeled test container or network remained.

## Known limitations and risks

- Profile labels in this focused qualifier do not enforce distinct resource
  ceilings.
- The ephemeral Ed25519 signing key proves artifact integrity within the
  qualifier, not release trust-root promotion.
- This evidence covers the Docker slice only, not the complete environment
  matrix.

## Recommended next entry point

Add persistent owner-visible environment records and exact start/inspect/cleanup
controls, then qualify a process/API and real-browser adapter under enforced
resource profiles.
