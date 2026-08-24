# ADR 0197: Signed multi-attachment integration egress

Status: Accepted

Extends: ADR 0196.

## Context

ADR 0196 established that allowlisted integration egress requires trusted byte
accounting, but left the privileged enforcement service and runtime adapters
unimplemented. A proxy environment variable alone cannot prevent direct
sockets. Independently opening one proxy for a process branch and another for
a Docker branch would also double the admitted byte budget.

The unprivileged product installation cannot safely become a root execution
source. The user must be able to choose whether this authority exists without
making normal FAM_OS installation equivalent to host-network authority.

## Decision

Allowlisted egress uses one device-signed
`IntegrationNetworkEnforcementRequest`. It binds the request, permit,
environment, exact host, principal, session, authorization evidence, complete
plan digest, ordered attachment kinds, canonical host-and-port allowlist,
aggregate byte ceiling, expiry, and signer identity.

The external Unix broker accepts only the configured Core UID in the configured
exact unified-cgroup-v2 path. It verifies the Ed25519 request before durable
state or Supervisor effects. A temporary deterministic Supervisor grant is
bound to the request and enforcement identity, used only for open, observe,
close, or recover, and retired at terminal state. Every Supervisor operation
has mandatory requested/succeeded/failed hash-chain audit events.

The privileged enforcement adapter may create a Linux namespace attachment, a
Docker IPv6-only internal network attachment, or both. Candidate output policy
permits only a credential-free CONNECT proxy. Docker host-input and forwarding
policy permits the proxy, same-bridge service traffic, and established replies,
then drops new bypass traffic. Domain resolution accepts only global addresses;
explicit IP literals remain exactly owner-authorized. Proxy accounting consumes
the aggregate transmitted-plus-received quota before forwarding and terminates
on exhaustion or expiry.

One mixed environment opens one broker lease before either backend. All
attachments use listeners backed by one thread-safe quota, and the composite
orchestrator owns terminal close/recovery. Durable `network_opening` intent is
written before the broker call so response loss is recoverable, while invalid
or substituted plans fail before broker contact.

Network power is opt-in. Core composes its signer and client only when the owner
sets an absolute broker socket. The owner can export the persistent device
public key, never the private key. The broker system unit refuses an
owner-writable runtime and requires a separately provisioned root-owned
`/usr/libexec/fam-os-network/bin/fam-network-broker`, which revalidates that
root-owned signed installation before serving.

## Consequences

- Process, Docker, and mixed source adapters can consume exact broker
  attachments without receiving privileged sessions.
- A same-UID process outside the configured Core cgroup cannot use the socket.
- Missing signer, broker, provider, attachment, finalized accounting, or exact
  scope fails closed.
- CONNECT-only enforcement does not provide UDP or transparent arbitrary socket
  access.
- Docker availability does not imply Docker allowlisted egress; the broker must
  be deliberately provisioned with the required host controls.
- This decision is source-validated architecture. It is not installed root
  enforcement evidence and does not complete Phase 27.13.

## Alternatives considered

- **Proxy variables only:** rejected because candidates can bypass them.
- **One broker lease per backend:** rejected because it duplicates the approved
  quota and complicates terminal evidence.
- **Execute the owner installation as root:** rejected because an owner-writable
  Python path is a privilege-escalation path.
- **Trust Docker `--internal` alone:** rejected because host-gateway and
  forwarding behavior also require exact policy and negative qualification.

## Evidence

- `src/fam_os/adapters/integration/network_broker_service.py`
- `src/fam_os/adapters/integration/multi_network_enforcement.py`
- `src/fam_os/adapters/integration/docker_network_enforcement.py`
- `src/fam_os/adapters/linux/network_namespace.py`
- `src/fam_os/supervisor/network_proxy.py`
- `src/fam_os/supervisor/network_proxy_runtime.py`
- `src/fam_os/adapters/integration/composite_environment.py`
- `src/fam_os/product/composition/integration_network.py`
- `docs/operations/INTEGRATION_NETWORK_BROKER.md`
- Handoff 0230
