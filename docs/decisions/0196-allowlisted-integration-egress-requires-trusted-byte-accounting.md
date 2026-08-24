# ADR 0196: Allowlisted integration egress requires trusted byte accounting

Status: Accepted

Extends: ADR 0183 and ADR 0194.

## Context

Integration plans already bind exact network hosts and a maximum network-byte
impact, but receipts had no destination or byte-accounting evidence. The
concrete process and Docker adapters correctly rejected allowlisted mode.
Setting proxy environment variables, filtering DNS answers, or validating a
receipt after unrestricted launch would not enforce the admitted boundary.

## Decision

Successful allowlisted environments must carry an
`IntegrationNetworkUsage` issued by a trusted deterministic enforcement
boundary. It binds an enforcement identity, exact environment, observed
destinations, transmitted and received byte counts, the exact admitted byte
ceiling, quota state, observation time, and evidence digest.

Core validates the evidence after launch and cleanup. Destinations must remain
a subset of the approved host names, the byte ceiling must exactly equal the
plan, and quota exhaustion can never produce a successful result. Cleanup
requires finalized accounting. Non-allowlisted plans may not claim this
evidence.

Core also defines a replaceable broker port with bounded `open`, `observe`,
`close`, and interruption-safe `recover` operations. An open request binds the
exact permit, plan digest, host, attachment kind, destinations, byte ceiling,
and expiry. The returned lease must preserve every bound field and identifies
only a credential-free internal proxy URI and a provider-specific attachment.
The Unix client length-bounds both directions and rejects contract, identity,
scope, limit, expiry, or finalization substitution.

The enforcement implementation must remain outside model execution and the
unprivileged candidate. It must prevent direct bypass, resolve destinations
without DNS-rebinding escape, account traffic before forwarding beyond the
remaining quota, and close deterministically during compensation and restart
recovery. A local HTTP proxy setting alone is not this boundary.

## Consequences

- Existing Docker and process adapters continue to fail closed for allowlisted
  mode until a concrete external broker satisfies this contract.
- An environment cannot be marked ready from unaccounted or post-hoc network
  observations.
- The receipt and Shell response schemas gain an optional nested usage object;
  Core requires it precisely when the admitted plan uses allowlisted egress.
- This decision is source-validated architecture, not installed allowlisted
  egress evidence and not completion of Phase 27.13.
- The Unix client is not the privileged daemon; the daemon must authenticate
  the peer and use the deterministic Supervisor enforcement and audit path.

## Evidence

- `src/fam_os/core/engineering/integration_network.py`
- `src/fam_os/core/engineering/integration_environment_service.py`
- `src/fam_os/core/engineering/integration_environment_ports.py`
- `src/fam_os/adapters/integration/network_broker.py`
- `schemas/v1alpha1/fam.core.integration-network-usage.schema.json`
- `tests/unit/test_integration_environment.py`
- `tests/unit/test_integration_environment_service.py`
- `tests/unit/test_integration_network_broker.py`
- Handoff 0229
