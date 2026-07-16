# FAM_OS system threat model

## Security claim

FAM_OS is an unprivileged, owner-controlled Linux intelligence service. Models,
experts, connectors, remote devices, retrieved content, and generated output are
untrusted. Deterministic admission, permission, verification, audit, package
trust, and Supervisor policy mediate every effect. FAM_OS does not protect an
owner from host root, a compromised kernel, firmware, or physical attacks.

## Assets and boundaries

Protected assets are user content and memory, credentials, application state,
model and verifier integrity, permission grants, audit history, hardware
availability, and accepted results. Boundaries are: local client to Core; Core
to Supervisor; Core to model/expert; Core to application connector; verifier to
sandbox; package repository to activation; local device to trusted remote
device; and one Linux user to another.

## Attacker classes

- malicious prompt, retrieved document, model output, expert, or connector;
- unauthorized local process or different Linux user;
- compromised enrolled device or network peer;
- tampered package, schema, configuration, verifier, update, or audit ledger;
- resource-exhaustion and crash-loop input;
- confused or hurried owner approving an effect without adequate context.

## Threat register

| Boundary | Threat | Required control | Verification |
|---|---|---|---|
| Client/Core | forged session, replay, oversized input | authenticated local identity, bounded typed frames, monotonic lifecycle | transport and contract tests |
| Model/Core | prompt injection becomes authority | model output is proposal data; closed capability registry; explicit approval | lifecycle and authorization tests |
| Connector/Core | connector bypasses permission or lies about action | scoped grants, action audit, deterministic postconditions | application safety acceptance |
| Core/Supervisor | intelligence obtains privileged control | minimal deterministic API, owned-service namespace, capability checks | Supervisor threat suite |
| Verifier/host | generated code escapes or exhausts host | Bubblewrap namespaces, no network/home, cgroups, rlimits, fail closed | sandbox probe |
| Package/runtime | substitution, downgrade, partial update | signed manifests, digest binding, atomic activation and rollback | package and update tests |
| Memory/user | cross-user disclosure, undeletable data | owner-bound encryption and roots, scoped retrieval, export/delete/reset | memory privacy tests |
| Fabric/network | impersonation, replay, context over-sharing | enrollment, signed ephemeral handshake, AEAD sequence, deny-default context | trusted-fabric demo |
| Audit/storage | deletion, rollback, disk exhaustion | chained private ledger, bounded retention, exported head; explicit residual risk | integrity and soak tests |
| Hardware | thermal, RAM, storage, task exhaustion | live budgets, headroom, adaptive throttling, crash backoff | production soak |
| UI/human | ambiguous approval or hidden action | preview, scope, reversibility, capability provenance, result evidence | Shell/Console acceptance |

## Mandatory fail-closed invariants

Unknown identity, capability, package digest, schema version, verifier, resource
measurement, postcondition, or recovery state cannot produce an accepted
result. Remote partial output is discarded. Recovery mode cannot execute
application actions, train experts, mutate memory, or use the network.

## Residual risks

Same-user processes can attack other same-user resources unless a stronger
container or dedicated account is configured. Linux namespace containment is
not a VM. A fully compromised enrolled device can disclose context explicitly
authorized for it. The local audit ledger is tamper-evident, not deletion-proof.
Accessibility and screen-input fallbacks have lower semantic assurance. These
limits must remain visible in product diagnostics and must not be described as
multi-tenant hostile-code isolation.
