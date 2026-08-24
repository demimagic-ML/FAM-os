# Handoff 0211: Installed database authority chain

**Date:** 2026-07-19  
**Plan step:** Phase 27.12 installed qualification  
**Status:** Partial  
**Previous handoff:** `0210-owner-engineering-authority-surfaces.md`

## Objective

Prove that the signed installed package can traverse the real owner authority,
database mutation, audit, restart, reconfirmation, and revocation chain.

## Scope completed

- Added one integration scenario using production secure storage, owner-key
  encryption, persistent grants, the real Console HTTP boundary, the real Shell
  Unix-socket boundary, Core dual-authority database admission, and the concrete
  SQLite adapter.
- Proved a verified migration with encrypted backup and restore rehearsal.
- Retrieved the persisted authorization audit and confirmed all recorded
  decisions allowed the executed effect.
- Restarted secure storage and proved the active grant became visible but
  unusable and reconfirmation-required.
- Issued a fresh Shell-session-bound context, reconfirmed the exact grant,
  revoked it, and proved a subsequent database execution was denied before
  adapter mutation.
- Added a dedicated build/sign/install qualifier that runs from a fresh wheel
  and records installed module identity, wheel and signer digests, profile
  results, and physical host/cgroup observations.

## Explicitly not completed

- PostgreSQL and MySQL adapters and qualification.
- Profile-specific cgroup enforcement inside the dedicated qualifier; the two
  declared profile scenario runs executed on one measured unrestricted host.
- Independent second-host evidence.
- Phase 27.12 exit gate.

## Files changed

| Path | Purpose |
|---|---|
| `tests/integration/test_installed_database_authority_chain.py` | Real end-to-end authority/database lifecycle |
| `tests/integration/installed_database_authority_support.py` | Bounded fixture and local transport support |
| `tools/run_phase27_database_authority_qualification.py` | Dedicated signed installed qualifier |
| `tools/run_phase31_signed_engineering.py` | Expanded aggregate installed suite |
| `artifacts/engineering/phase27/database-authority-installed-20260719-attempt3.json` | Passing signed installed evidence |
| `artifacts/engineering/phase31/signed-installed-engineering-20260719-authority-db.json` | Preserved aggregate failure evidence |

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.integration.test_installed_database_authority_chain -v
```

Result: 1 real lifecycle scenario passed in 1.17 seconds.

```bash
.verification-venv/bin/python \
  tools/run_phase27_database_authority_qualification.py \
  --output artifacts/engineering/phase27/database-authority-installed-20260719-attempt3.json \
  --repository . --builder-python .verification-venv/bin/python
```

Result: passed. Both declared profile scenario executions passed from
`site-packages`; wheel SHA-256 is
`c32cc916af53a86b07d1f1bd024767e5c854d9fa43434750b8e462c80c0c0cdb`
and signer public-key SHA-256 is
`e824bf8e23bf88bfd2019887f83ee99e07de1f5ada0a975cccacc2b32bc90068`.

The measured host had 24 logical CPUs, 65,447,104 KiB RAM, kernel
6.17.0-35-generic, and an unlimited current cgroup CPU/memory ceiling.

## Failed experiment retained

The expanded Phase 31 aggregate installed run reached 123 tests and the new
database authority lifecycle passed, but the aggregate correctly failed because
`test_wheel_style_root_falls_back_to_packaged_verifier_defaults` rejected the
current environment. The artifact remains as failed evidence and is not used to
claim the Phase 31 gate.

## Known limitations and risks

- Declared profile labels are not substitutes for separate enforced resource
  envelopes or independent hardware.
- The product currently implements candidate SQLite only; remote engine
  contracts do not imply working remote adapters.
- The installed evidence proves this bounded lifecycle, not the full
  engineering fabric or 24-hour soak.

## Recommended next entry point

Implement PostgreSQL integration-environment migration, backup, restore,
compensation, cancellation, and hostile tests behind an opaque connection
secret adapter. Then repeat this installed lifecycle under an enforced
`compat-cpu-16gb` service cgroup and the full workstation profile.
