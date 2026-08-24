# ADR 0195: Integration start-intent audit is owner-visible and read-only

Status: Accepted

Extends: ADR 0194.

## Context

ADR 0194 made start intents and recovery receipts encrypted and durable, but
only product startup and secret lifecycle policy could inspect them. The owner
could see normal active/cleaned environments while a committed, failed,
recovery-required, or recovered pre-result lifecycle remained invisible.

## Decision

The product environment facade exposes owner-scoped list and exact inspection
of all start intents. These are read-only audit operations. No surface may edit
intent state, replace a permit, forge recovery evidence, or trigger recovery
outside the existing deterministic startup/secret-retirement lifecycle.

Console serves authenticated GET-only routes under
`/api/v1/engineering/environment-start-intents`. Normal loopback session and
host checks apply. Responses include state, typed plan and candidate, the exact
permit when present, and the terminal recovery receipt when present. They never
include encrypted tokens, secret values, connector sessions, or adapter-private
journals.

Shell adds `intent_list` and `intent_inspect` to the existing strict
`fam.shell.integration-environment/v1alpha1` query/response roots. A typed
`ShellIntegrationStartIntentRecord` validates state-dependent shapes: a
prelaunch failure has no permit, permitted states require one, and only a
recovered state carries a recovery receipt. Transport remains the owner-UID
mode-0600 Unix socket.

## Consequences

- The owner can audit committed, prelaunch-failed, recovery-required,
  recovered, and still-starting intent metadata through both local clients.
- Visibility does not grant execution, cleanup, or recovery authority.
- Signed installed tests prove a committed secret-bearing process intent is
  visible through Console and Shell without its secret value, and a real
  recovered mixed intent exposes exact terminal cleanup evidence through
  Console.
- Pagination is not yet required because integration environments are bounded
  and owner-local; a future retention policy may add pagination without
  changing lifecycle authority.

## Evidence

- `src/fam_os/console/integration_start_intent_routes.py`
- `src/fam_os/shell/integration_environment_contracts.py`
- `src/fam_os/adapters/shell/integration_environment_dispatch.py`
- `schemas/v1alpha1/fam.shell.integration-environment-query.schema.json`
- `schemas/v1alpha1/fam.shell.integration-environment-response.schema.json`
- `tests/integration/test_console_integration_environments.py`
- `tests/unit/test_fam_shell_integration_environment_transport.py`
- `tests/integration/test_installed_process_owner_restart_chain.py`
- `tests/integration/test_real_mixed_integration_environment.py`
- `artifacts/engineering/phase27/integration-environment-installed-20260719-attempt14.json`
