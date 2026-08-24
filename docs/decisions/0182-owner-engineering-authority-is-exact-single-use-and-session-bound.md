# ADR 0182: Owner engineering authority is exact, single-use, and session-bound

Status: Accepted

## Context

ADR 0181 preserves encrypted grant visibility across restart while deliberately
restoring no live mutation authority. A repository reconfirmation bit is not an
authentication ceremony and must not become a client operation. FAM Console and
FAM Shell need a production-reachable way for the local owner to inspect,
activate, revoke, and audit bounded authority without giving either client
direct access to storage or to the policy ledger.

## Decision

The product composes one `PersistentEngineeringAuthorizer` and one
`OwnerEngineeringAuthenticationRegistry` above the encrypted grant repository.
The registry issues two-minute, in-memory, single-use contexts for exactly one
owner, purpose, payload digest, and authenticated transport session. Grant and
break-glass contexts are separate. A mismatch or attempted use consumes the
context without granting authority.

Grant activation must carry strict schema envelopes for the grant, owner
approval, and, where required, the exact break-glass challenge and decision.
Both context identifiers must belong to the same authenticated Console or Shell
session performing activation. The deterministic grant policy then validates
the complete scope and consequences before the repository can be marked usable.

Console exposes the facade only over loopback after bootstrap-token exchange,
HttpOnly session authentication, Host and Origin checks, CSRF validation, and
an explicit confirmation field. Shell exposes typed request and response roots
over the owner-UID, mode-0600 Unix socket. Neither surface exposes
`mark_reconfirmed`, grant consumption, repository writes, or authorization
decision creation.

The shared live authorizer serializes activation, authorization, revocation,
and consumption. Every execution authorization decision, including denial, is
persisted in the encrypted ordered audit trail. Restart invalidates all active
grant usability and discards all authentication contexts.

## Consequences

- Durable grant visibility cannot independently recreate execution power.
- Copying a fresh authentication context into another Console or Shell session
  cannot activate a grant.
- High-risk grants require two independently scoped, single-use owner contexts.
- Revocation is immediately visible to the same shared live policy and durable
  store.
- The installed Console and Shell compositions can reach the owner authority
  facade, but installed both-profile qualification is still required before an
  operational claim.

## Evidence

- `src/fam_os/product/owner_engineering_authentication.py`
- `src/fam_os/product/engineering_authority.py`
- `src/fam_os/product/engineering_authority_api.py`
- `src/fam_os/console/engineering_authority_routes.py`
- `src/fam_os/shell/engineering_authority_contracts.py`
- `src/fam_os/adapters/shell/engineering_authority_dispatch.py`
- `tests/unit/test_engineering_authority_api.py`
- `tests/integration/test_console_engineering_authority.py`
- `tests/unit/test_fam_shell_engineering_authority_transport.py`
