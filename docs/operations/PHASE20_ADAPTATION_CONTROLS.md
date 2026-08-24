# Phase 20.7 live adaptation controls

FAM_OS exposes live adaptation as an owner-controlled local service, not as
hidden model state. The control state shows whether adaptation is enabled, the
active and known-good snapshot for each workflow, drifted snapshot identities,
the current revision, and the last operation.

## FAM Shell

Inspection commands are read-only and paginated:

```text
/adaptation status
/adaptation snapshots [OFFSET LIMIT]
/adaptation prewarms [OFFSET LIMIT]
/adaptation health [OFFSET LIMIT]
/adaptation drift [OFFSET LIMIT]
/adaptation receipts [OFFSET LIMIT]
```

Mutations require the literal confirmation flag:

```text
/adaptation enable --confirm
/adaptation disable --confirm
/adaptation evaluate intent:code --confirm
/adaptation rollback intent:code --confirm
/adaptation reset --confirm
```

Missing confirmation fails safely. Disable retains evidence but returns request
selection and context to the baseline policy. Reset removes learned behavior and
its derived health/drift data while preserving terminal task results and control
receipts.

## FAM Console

The **Resident intelligence** panel shows the same authoritative state and
ledgers. Its controls use the authenticated loopback Console session, same-origin
checks, and CSRF token. The HTTP API is:

```text
GET  /api/v1/adaptation/status
GET  /api/v1/adaptation/snapshots?offset=0&limit=100
GET  /api/v1/adaptation/prewarms?offset=0&limit=100
GET  /api/v1/adaptation/health?offset=0&limit=100
GET  /api/v1/adaptation/drift?offset=0&limit=100
GET  /api/v1/adaptation/receipts?offset=0&limit=100
POST /api/v1/adaptation/enable
POST /api/v1/adaptation/disable
POST /api/v1/adaptation/reset
POST /api/v1/adaptation/workflows/{workflow}/evaluate
POST /api/v1/adaptation/workflows/{workflow}/rollback
```

Mutation bodies contain exactly `request_id` and boolean `confirmed`. Request
identity makes replay idempotent.

## Drift behavior

FAM_OS requires at least two health samples for both baseline and candidate. It
evaluates verification quality, P95 latency, policy violations, and temperature
when a thermal source is available. A regressing candidate is durably marked
drifted and the known-good snapshot becomes active in the same transaction.
Unavailable thermal evidence is reported separately and does not erase the
quality, latency, or policy evaluation.

The latest verified snapshot may be prewarmed without becoming active advice.
Prewarm remains prompt-free, resource-admitted, non-evicting, and blocked while
adaptation is disabled or for a snapshot already marked drifted.

## Qualification

Run the signed installed exit:

```bash
PYTHONPATH=src .verification-venv/bin/python -m tools.run_phase20_adaptation_control_exit
```

The runner builds and installs a fresh Ed25519-signed seven-component release.
It proves Shell and Console inspection, two prompt-free prewarms, a 2,048-token
adapted canary, a 32,768-token disabled request, healthy promotion, repeated
quality/latency/thermal/policy regression, automatic known-good rollback,
confirmation denial, disabled-state restart persistence, confirmed manual
rollback and reset, retention of ten terminal results, encrypted database
content, healthy diagnosis, and complete removal. Raw evidence is written to
`artifacts/adaptation/phase20.7-control-and-rollback.json`.
