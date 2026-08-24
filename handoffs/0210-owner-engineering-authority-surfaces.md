# Handoff 0210: Owner engineering authority surfaces

**Date:** 2026-07-19  
**Plan step:** Phase 27.12 production authority dependency  
**Status:** Partial  
**Previous handoff:** `0209-persistent-engineering-grants-and-audit.md`

## Objective

Make encrypted restart-safe engineering grants controllable through the
installed owner surfaces without exposing storage reconfirmation or widening
authority after restart.

## Scope completed

- Added two-minute, single-use owner authentication contexts bound to the exact
  purpose, payload digest, and Console or Shell authority session.
- Added a product facade for context issuance, strict grant activation,
  inspection, audit retrieval, and confirmed revocation.
- Composed the facade once with the persistent grant repository and shared live
  authorizer; database engineering consumes that same authorizer.
- Added loopback Console routes behind existing session, Host, Origin, CSRF,
  exact-field, and explicit-confirmation controls.
- Added five strict Shell schema roots and owner-UID Unix-socket dispatch for
  the same operations.
- Serialized shared live-authorizer state transitions across Console, Shell,
  and execution requests.
- Kept repository reconfirmation, consumption, raw writes, and audit-decision
  creation absent from both client surfaces.

## Explicitly not completed

- Installed signed-artifact execution of the new Console and Shell routes.
- Both validation-profile evidence for database engineering.
- Remote database-engine adapters and qualification.
- Phase 27.12 exit gate.

## Architecture and decisions

ADR 0182 makes fresh authority exact, single-use, and transport-session-bound.
ADR 0181 remains the durable restart rule: persisted active grants become
reconfirmation-required before product services start.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/product/owner_engineering_authentication.py` | Session-bound single-use owner contexts |
| `src/fam_os/product/engineering_authority.py` | Serialized persistent live policy |
| `src/fam_os/product/engineering_authority_api.py` | Bounded product owner facade |
| `src/fam_os/product/composition/storage_unit.py` | Facade dependencies |
| `src/fam_os/product/service.py` | Database, Console, and Shell production composition |
| `src/fam_os/console/engineering_authority_routes.py` | Authenticated owner HTTP routes |
| `src/fam_os/console/http.py` | Console route composition |
| `src/fam_os/shell/engineering_authority_contracts.py` | Strict Shell request/response roots |
| `src/fam_os/adapters/shell/engineering_authority_dispatch.py` | Shell-to-product mapping |
| `src/fam_os/shell/wire.py` | Engineering wire kinds and codecs |
| `src/fam_os/adapters/shell/client.py` | Owner client methods |
| `src/fam_os/adapters/shell/dispatcher.py` | Server dispatch and stable errors |
| `src/fam_os/schemas/catalog.py` | Five registered schema roots |
| `tests/unit/test_engineering_authority_api.py` | Product ceremony and cross-session denial |
| `tests/integration/test_console_engineering_authority.py` | HTTP authentication and CSRF evidence |
| `tests/unit/test_fam_shell_engineering_authority_transport.py` | Strict owner-socket transport evidence |

## Public interfaces

- `ProductEngineeringAuthorityApi`
- `ShellEngineeringContextRequest`
- `ShellEngineeringActivationRequest`
- `ShellEngineeringGrantQuery`
- `ShellEngineeringRevocationRequest`
- `ShellEngineeringAuthorityResponse`
- Console routes under `/api/v1/engineering/`

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_fam_shell_engineering_authority_transport \
  tests.unit.test_engineering_authority_api \
  tests.unit.test_owner_engineering_authentication \
  tests.integration.test_console_engineering_authority \
  tests.contract.test_schema_roundtrip \
  tests.contract.test_schema_compatibility
```

Result: 36 tests passed.

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_fam_shell_adaptation_transport \
  tests.unit.test_fam_shell_peer_transport \
  tests.unit.test_fam_shell_memory_transport
PYTHONPATH=src python3 -m unittest discover \
  -s tests/architecture -p 'test_*boundary.py'
```

Result: 12 existing Shell regression tests and 39 architecture tests passed.

A broader product-service batch passed 9 tests and failed 4 before exercising
this change because the environment's installed `cryptography` certificate
object lacks `not_valid_before_utc`. That dependency mismatch is not counted as
authority-route evidence.

## Known limitations and risks

- Local owner authentication inherits the existing Console bootstrap-token and
  Shell peer-UID guarantees; a future remote owner surface must define a new
  transport identity and cannot reuse these contexts.
- Authentication contexts are intentionally volatile and are lost on restart.
- Source composition and focused tests do not satisfy installed operational
  qualification.

## Recommended next entry point

Build and install a signed artifact, exercise real context issuance,
activation, database execution, audit retrieval, revocation, restart denial,
and fresh reconfirmation through both owner surfaces under both validation
profiles. Then implement and qualify the declared remote database engines.
