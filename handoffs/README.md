# FAM_OS Handoffs

Handoffs are the append-only implementation history for major changes.

## Required workflow

Before starting major work:

1. Read `../AGENTS.md`.
2. Read `../MASTER_PLAN.md`.
3. Read the newest relevant handoff.
4. Identify the exact plan step being advanced.

Before ending major work:

1. Copy `HANDOFF_TEMPLATE.md` to the next numbered filename.
2. Fill every applicable section with concrete evidence.
3. Include exact commands and outcomes.
4. Update the master plan.
5. Link relevant raw artifacts and ADRs.

## Naming

```text
0001-project-foundation.md
0002-prototype-map-and-contract-foundation.md
0003-application-weaving-boundary.md
0004-linux-hardware-discovery.md
0005-ollama-inference-adapter.md
0006-systemd-cgroup-supervisor-adapters.md
0007-python-verifier-sandbox.md
0008-verified-code-orchestration.md
0009-phase1-measured-parity.md
0010-parent-prototype-read-only.md
0011-full-hardware-and-mcp-plan.md
0012-application-fabric-contracts.md
0013-core-execution-plan-contracts.md
0014-hardware-resource-contracts.md
0015-component-manifest-contracts.md
0016-structured-failures-degradation.md
0017-strict-schema-compatibility.md
0018-configuration-layering.md
0019-dual-validation-profiles.md
0020-profile-driven-benchmark-composition.md
0021-full-workstation-smoke-baseline.md
0022-supervisor-boundary.md
0023-owned-service-lifecycle.md
0024-applied-resource-limits.md
0025-capability-access-grants.md
0026-strong-model-quality-rerun.md
0027-immutable-supervisor-audit.md
0028-safe-service-recovery.md
0029-supervisor-threat-model.md
0030-core-request-admission.md
0031-core-routing-lifecycle.md
0032-core-plan-state-machine.md
0033-core-authorized-application-steps.md
0034-core-confirmation-transitions.md
0035-core-attempt-transitions.md
0036-core-control-transitions.md
0037-core-final-result-policy.md
0038-core-lifecycle-matrix.md
0039-application-capability-registry.md
0040-authenticated-application-transport.md
0041-mcp-client-application-adapter.md
0042-permission-filtered-local-mcp-server.md
0043-linux-application-discovery.md
0044-deterministic-linux-capabilities.md
0045-linux-accessibility-bridge.md
0046-fam-shell-mvp.md
0047-native-vscode-semantic-connector.md
0048-restricted-screen-input-fallback.md
0049-required-application-action-safety.md
0050-cross-application-acceptance.md
0051-expert-manifest-capability-namespace.md
0052-local-expert-registry.md
0053-package-trust-validation.md
0054-expert-hardware-compatibility.md
0055-strong-model-regression-requirement.md
0056-durable-expert-package-lifecycle.md
0057-expert-routing-benchmark-metadata.md
0058-reference-expert-packages.md
```

Use the next sequence number. Never reuse a number or rewrite an older handoff to represent newer work.

## Scope

Create one handoff per coherent major change, not one per file and not one vague handoff covering unrelated changes.
