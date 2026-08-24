# Handoff 0229: Allowlisted egress accounting contract

**Date:** 2026-07-19  
**Plan step:** Phase 27.13 allowlisted network enforcement  
**Status:** Partial  
**Previous handoff:** `0228-owner-visible-integration-intent-audit.md`

## Objective

Close the Core evidence gap that previously allowed no trustworthy proof of
allowlisted destinations or byte-budget enforcement.

## Scope completed

- Added strict destination and bidirectional byte-accounting evidence.
- Required the evidence for successful allowlisted starts.
- Required exact plan/environment/limit binding and approved destinations.
- Prevented quota-exceeded evidence from producing a successful result.
- Required finalized accounting on cleanup.
- Rejected network evidence on denied or isolated plans.
- Required a positive byte budget for every allowlisted plan.
- Added and rendered a standalone public schema plus nested receipt schemas.
- Added exact network-enforcement request and lease contracts.
- Added a replaceable open/observe/close/recover broker port.
- Added a length-bounded Unix client that rejects substituted responses and
  unfinalized close/recovery evidence.

## Explicitly not completed

- The deterministic external egress broker and its privileged lifecycle.
- Process or Docker wiring; both adapters continue to reject allowlisted mode.
- DNS-rebinding, proxy-bypass, quota-exhaustion, restart, and installed physical
  positive/negative qualification.
- Portable browser packaging, independent profiles, soak, and human review.

## Architecture and decisions

ADR 0196 requires enforcement-owned evidence and explicitly rejects proxy
environment variables or post-hoc counters as the permission boundary.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/integration_network.py` | Strict usage contract and plan validator |
| `src/fam_os/core/engineering/integration_environment.py` | Positive allowlist byte budget |
| `src/fam_os/core/engineering/integration_environment_receipts.py` | Optional typed usage evidence |
| `src/fam_os/core/engineering/integration_environment_service.py` | Start/cleanup evidence enforcement |
| `src/fam_os/core/engineering/integration_environment_ports.py` | Replaceable enforcement broker port |
| `src/fam_os/core/engineering/__init__.py` | Public export |
| `src/fam_os/adapters/integration/network_broker.py` | Bounded external broker client |
| `src/fam_os/schemas/catalog.py` | Standalone schema registration |
| `schemas/v1alpha1/fam.core.integration-network-usage.schema.json` | Rendered strict contract |
| `tests/unit/test_integration_environment.py` | Contract bounds |
| `tests/unit/test_integration_environment_service.py` | Core fail-closed admission |
| `tests/unit/test_integration_network_broker.py` | Exact transport and substitution denial |

## Public interfaces

- `IntegrationNetworkUsage`
- `IntegrationNetworkEnforcementRequest`
- `IntegrationNetworkLease`
- `IntegrationNetworkEnforcementBroker`
- `UnixIntegrationNetworkBroker`
- `validate_integration_network_usage(...)`
- `IntegrationEnvironmentReceipt.network_usage`
- `fam.core.integration-network-usage/v1alpha1`

## Validation

```bash
PYTHONPATH=src python3 -m unittest \
  tests.unit.test_integration_environment \
  tests.unit.test_integration_environment_service \
  tests.unit.test_process_integration_environment \
  tests.unit.test_docker_integration_environment \
  tests.unit.test_mixed_integration_environment \
  tests.unit.test_product_integration_environment_api \
  tests.unit.test_integration_environment_repository \
  tests.integration.test_console_integration_environments \
  tests.unit.test_fam_shell_integration_environment_transport \
  tests.contract.test_integration_coverage \
  tests.contract.test_schema_compatibility
PYTHONPATH=src python3 -m unittest discover -s tests/architecture -t .
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
```

Result: 71 affected tests passed in 1.460 seconds; all 41 architecture tests
passed in 0.767 seconds; all 374 schema artifacts validate.

## Evidence and artifacts

- `docs/decisions/0196-allowlisted-integration-egress-requires-trusted-byte-accounting.md`
- `schemas/v1alpha1/fam.core.integration-network-usage.schema.json`

## Known limitations and risks

- This is source contract evidence only.
- A same-UID candidate cannot be trusted to report or enforce its own usage.
- A broker must handle direct sockets, redirects, DNS changes, CONNECT, and
  quota exhaustion rather than depending on client cooperation.

## Operational notes

No process, container, socket, network namespace, or privileged service was
started by this change.

## Recommended next entry point

Implement the authenticated deterministic privileged broker service with
mandatory Supervisor audit, then add deliberate bypass and byte-exhaustion
tests before wiring either runtime adapter.
