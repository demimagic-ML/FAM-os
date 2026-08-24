# ADR 0221: Natural integration health is changeset and post-apply evidence

Status: Accepted

## Context

FAM_OS already had typed process, API, browser, Docker, mixed-backend, secret,
network, cleanup, and restart-recovery machinery for integration environments.
Those components were reachable only when a caller constructed the complete
plan and invoked the dedicated Console or Shell controls. The natural master
engineering loop never selected or ran them, so a request such as “update the
site and preview it end-to-end” stopped after ordinary file verification.

An integration environment executes untrusted candidate content. A successful
health response alone is insufficient: the exact signed launch recipe,
candidate, prospective changeset, permit, service health, termination, and
cleanup evidence must all remain attached to the task. The owner tree must also
be tested independently after apply before a local commit can claim success.

## Decision

Core recognizes a narrow natural integration intent and includes the internal
`integration-environment` tool coordinate in the owner-visible grant scope. It
does not add a fake repository toolchain and does not grant network, secret, or
production authority.

The initial natural planner supports one exact static-web vertical slice. It
requires a regular candidate HTML file and selects a release-signed named
Python static-server recipe. The plan binds one loopback port, denied external
egress, finite memory/CPU/process/time budgets, the exact candidate, host,
task, and prospective changeset identity. Unsupported repositories fail
truthfully instead of receiving a generic service plan.

Integration authorization is checked against the owner workspace named by the
grant, while execution remains confined to its isolated candidate derivative.
Candidate paths do not become hidden alternate grant roots.

The natural coordinator starts through the existing owner-encrypted product
environment API, requires `READY`, immediately performs mandatory cleanup,
requires `CLEANED`, and records the cleanup receipt in the master loop. A
candidate integration receipt may satisfy verification only for that exact
signed integration lifecycle. The changeset preview includes its receipt ID.
After apply, Core creates a fresh clone from the owner workspace, repeats the
environment lifecycle, and records a distinct post-apply receipt before commit.
Restart/retry reuses an exact already-cleaned environment and never relaunches
it under the same identity.

Console and Shell master-loop projections expose candidate and post-apply
integration receipt IDs. The natural Console outcome includes the typed plan,
start result, cleanup receipt, and accurate receipt counts.

## Consequences

- Natural language can now invoke a real bounded integration lifecycle without
  callers constructing low-level environment contracts.
- Owner workspace mutation still waits for the exact changeset approval.
- Candidate service health and cleanup become part of the displayed checkpoint
  and local commit evidence.
- Post-apply service health is observed from a fresh owner-derived clone rather
  than inferred from candidate success.
- Network destinations, credentials, containers, browsers, and production
  systems remain unavailable unless their separate exact authorities and
  planners are composed.
- The current loopback port is selected before launch; eliminating the small
  reservation race remains part of the broader dynamic-port work in Phase
  27.13.
- A new signed installed release is required before this source composition can
  be called installed evidence.

## Alternatives considered

- Treat ordinary unit tests as integration-environment evidence: rejected
  because they do not prove service startup, health, bounds, or cleanup.
- Run the environment after apply only: rejected because the owner would be
  mutated before candidate service behavior entered the approval checkpoint.
- Reuse candidate success as post-apply proof: rejected because owner-tree
  drift and apply defects would be invisible.
- Infer arbitrary launch commands from model output or repository text:
  rejected because untrusted content cannot define executable authority.
- Add network or secret authority automatically for “end-to-end”: rejected
  because those powers require separate visible owner ceremonies.

## Evidence

- `src/fam_os/adapters/integration/natural_planning.py`
- `src/fam_os/product/natural_engineering_integration.py`
- `src/fam_os/product/natural_engineering_execution.py`
- `src/fam_os/product/natural_engineering_api.py`
- `src/fam_os/core/engineering/candidate_changeset_service.py`
- `src/fam_os/core/engineering/master_loop.py`
- `tests/integration/test_natural_integration_environment.py`
- `tests/unit/test_natural_integration_environment.py`
- `tests/integration/test_installed_process_owner_restart_chain.py`
