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
0041-local-mcp-client-adapter.md
0042-authenticated-mcp-core-ingress.md
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
0127-final-integration-rebaseline.md
0128-private-sqlite-wal-storage.md
0129-owner-bound-product-encryption.md
0130-durable-core-repositories-partial.md
0131-durable-core-repositories-complete.md
0132-restart-safe-action-reconciliation.md
0133-managed-ollama-runtime.md
0134-profile-derived-worker-cgroups.md
0135-signed-complete-release-installation.md
0136-installed-unified-core-gateway.md
0137-signed-live-expert-catalog-and-responsive-workers.md
0138-production-application-fabric-and-console.md
0139-permission-filtered-production-mcp-ingress.md
0140-explicit-production-desktop-fallbacks.md
0141-phase19-signed-application-weaving-exit.md
0142-production-declared-verifier-bindings.md
0143-production-ephemeral-session-memory.md
0144-production-expiring-document-indexing.md
0145-production-grounded-answers.md
0146-production-memory-management-controls.md
0147-production-verified-outcome-learning.md
0148-production-live-predictive-adaptation.md
0149-production-live-adaptation-controls.md
0150-production-persistent-peer-identity-and-mtls.md
0151-production-peer-state-and-owner-controls.md
0152-production-minimum-remote-context.md
0153-production-remote-core-route.md
0154-production-complete-remote-evidence.md
0155-production-remote-loss-recovery.md
0156-phase21-physical-qualification-kit.md
0157-installed-console-application-failure-recovery.md
0158-phase22-plan-and-production-failure-discovery.md
0159-governed-dataset-capture-and-synthesis.md
0160-real-qlora-backend-and-physical-smoke.md
0161-held-out-evaluation-and-signed-denial.md
0162-installed-console-terminal-and-scoped-observation.md
0163-installed-console-terminal-reconciliation.md
0164-installed-console-monotonic-task-updates.md
0165-typed-held-out-learning-curve.md
0166-real-expert-factory-signed-installed-exit.md
0167-final-phase22-release-and-browser-retest.md
0168-installed-conversation-first-console.md
0169-installed-current-request-ordering-fix.md
0170-action-intent-firewall-and-verified-directory-receipts.md
0171-console-workspace-context-and-secure-launch.md
0172-production-resource-policy-wiring.md
0173-production-residency-and-confirmed-eviction.md
0174-query-bound-extractive-grounding.md
0175-truthful-integration-coverage-refresh.md
0176-clean-built-artifact-profile-matrix.md
0177-production-action-restart-reconciliation.md
0178-phase23-installed-hardware-and-console-qualification.md
0179-installed-verifier-host-policy-and-total-removal.md
0180-phase23-lifecycle-diagnosis-and-tool-import-correction.md
0181-verifier-compatible-expert-scoped-runtime-routing.md
0182-exact-package-scopes-and-strict-json.md
0183-canonical-expert-archives-and-exact-verifiers.md
0184-owner-workspaces-and-tool-evidence-terminal.md
0185-bounded-workspace-tool-loop.md
0186-authenticated-console-launch-correction.md
0187-workspace-proposal-repair-and-escalation.md
0188-typed-engineering-authority-contracts.md
0189-strict-engineering-results-and-receipts.md
0190-engineering-authority-integration-surfaces.md
0191-owner-engineering-grants-and-assurance.md
0192-bounded-repository-intelligence-and-architecture.md
0193-transactional-candidate-workspaces.md
0194-signed-polyglot-execution-foundation.md
0195-complete-polyglot-dependency-and-privilege-layer.md
0196-verified-design-and-creative-assets.md
0197-controlled-git-and-remote-publication.md
0198-bounded-master-engineering-loop.md
0199-installed-engineering-security-qualification-partial.md
0200-engineering-completion-rebaseline.md
0201-bounded-runtime-diagnostic-adapter.md
0202-performance-and-diagnostic-qualification.md
0203-physical-diagnostic-toolchain.md
0204-stable-thread-sanitizer-pairs.md
0205-database-engineering-contracts.md
0206-candidate-sqlite-engineering-adapter.md
0207-sqlite-restart-reconciliation-and-fresh-rollback.md
0208-core-database-admission-and-aead-composition.md
0209-persistent-engineering-grants-and-audit.md
0210-owner-engineering-authority-surfaces.md
0211-installed-database-authority-chain.md
0212-integration-environment-contracts-and-admission.md
0213-bounded-docker-integration-adapter.md
0214-optional-product-docker-composition.md
0215-signed-installed-docker-environment.md
0216-persistent-owner-integration-environments.md
0217-bounded-process-api-integration-environments.md
0218-release-signed-integration-recipes.md
0219-corrected-installed-integration-lifecycle.md
0220-installed-owner-process-restart-chain.md
0221-bounded-real-browser-environment.md
0222-content-bound-retained-integration-artifacts.md
0223-restart-safe-process-secret-files.md
0224-owner-encrypted-engineering-secrets.md
0225-atomic-secret-revocation-and-environment-cleanup.md
0226-journaled-mixed-integration-environments.md
0227-intent-before-effect-integration-recovery.md
0228-owner-visible-integration-intent-audit.md
0229-allowlisted-egress-accounting-contract.md
0230-signed-multi-attachment-allowlisted-egress.md
0231-installed-engineering-loop-control-plane.md
0232-generated-content-review-and-incident-governance.md
0233-receipt-driven-master-lifecycle-driver.md
0234-durable-task-intent-and-active-preparation.md
0235-natural-language-verified-local-delivery.md
0236-signed-installed-natural-local-delivery.md
0237-builder-independent-signed-natural-lifecycle.md
0238-direct-installed-engineering-coverage.md
0239-history-preserving-natural-rollback.md
0240-separately-approved-natural-git-publication.md
0241-natural-failure-incident-attachment.md
0242-restart-safe-automatic-feature-branching.md
0243-integrated-signed-candidate-host-blocked.md
0244-trusted-review-passage-gate.md
0245-generated-documentation-apply-gate.md
0246-signed-installed-documentation-generation.md
0247-typed-incident-preservation-and-diagnosis.md
0248-postapply-failure-rollback-and-incident-closure.md
0249-bounded-candidate-repair-and-final-state-changesets.md
0250-automatic-governed-documentation-regeneration.md
0251-policy-selected-signed-independent-review.md
0252-owner-workspace-monitored-recovery-closure.md
0253-natural-runtime-diagnostic-composition.md
0254-natural-sqlite-database-engineering.md
0255-natural-shell-and-mcp-routing-correction.md
0256-natural-integration-environment-composition.md
0257-natural-fixed-template-multi-service-composition.md
0258-versioned-natural-service-declaration.md
0259-signed-installed-natural-service-composition.md
0260-natural-integration-resource-ceremony.md
0261-natural-postgresql-service-composition.md
0262-signed-installed-natural-postgresql-service.md
0263-natural-postgresql-migration-lifecycle.md
0264-generated-workspace-links-pruned.md
0265-installed-natural-cli-edit-create-and-run.md
0266-chatgpt-authenticated-codex-engineering-runtime.md
0267-session-bound-plan-followups-and-manifest-toolchains.md
```

Use the next sequence number. Never reuse a number or rewrite an older handoff to represent newer work.

## Scope

Create one handoff per coherent major change, not one per file and not one vague handoff covering unrelated changes.
