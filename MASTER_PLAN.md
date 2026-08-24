# FAM_OS Master Plan

## Purpose

This document is the authoritative implementation sequence for FAM_OS. Work must advance a named step, satisfy its exit gate, and create a handoff for every major change.

`MASTER_PLANv2.md` is the additive implementation sequence for Phases 24 and
later. It does not change the status or exit requirements of Phases 0–23.

The current Phase 30 governance continuation has release-signed deterministic
documentation generation through the ordinary candidate lifecycle and
source-composed automatic incident evidence preservation plus diagnosis. See
ADRs 0211–0212 and Handoffs 0246–0247. Documentation regeneration/trace
completion plus incident repair/monitored recovery and installed proof remain
open; neither milestone completes the Phase 30 or Phase 31 exit gates.

ADR 0213 and Handoff 0248 additionally connect a post-apply verification
failure to an exact owner-approved pre-commit rollback, typed incident report,
and closure without claiming a Git effect. ADR 0214 and Handoff 0249 add one
bounded verification-driven candidate repair, final-state changeset squashing,
sanitized diagnostic disclosure, typed remediation, and recovery closure. ADR
0217 and Handoff 0252 now keep repair recovery monitored until a distinct
post-apply owner-workspace reverification supplies the second observation,
report, and closure. Signed-installed proof and the final scenario matrix
remain open, so Phase 30.7 is not complete.

ADR 0215 and Handoff 0250 source-compose policy-selected generated-content
requirements, digest-bound governance files, automatic signed regeneration
inside the repair branch, historical stale-receipt preservation, current-output
admission, and truthful requirement/code/test/evidence traces. A new signed
installation and live production-verifier scenario remain open, so Phase 30.6
is still unchecked.

ADR 0216 and Handoff 0251 now source-compose deterministic review-discipline
selection, an Ed25519 release-signed independently identified reviewer, typed
remediation-plus-verification resolution receipts, and an exact
session-authenticated owner waiver with truthful reduced assurance. Real
repository integrations prove both signed passage and a blocking security
finding followed by waiver, apply, reverification, and local commit. A new
signed installation, live production-verifier proof, and the separate Phase
31.5 human review remain open, so Phase 30.8 is still unchecked.

## Current program status

**Integration incomplete.** Phases 0–15 are preserved as component,
acceptance, and narrow installed-operation evidence. They do not establish that
all documented fabrics are reachable from the installed product. Phases 16–23
are the final integration program; their detailed requirements are in
`NEXT_STEPS.md`, and current subsystem maturity is recorded in
`configs/integration/coverage.json`. See ADR 0111.

**Current execution point (2026-07-18): Phases 16–20, steps 21.1–21.6, and
Phase 22 are complete. Phase 21.7 still requires a second physical Linux
machine; Phase 23 final release qualification is the next local boundary.**
Phase 19.13 now closes the remaining local workspace-execution gap with a
Core-owned map, retrieve, typed patch, approval, re-observation, verification,
and reversal loop. Phase 21.6 binds
the immutable request/authority/plan/verifier acceptance digest into the remote
budget reservation, marks the attempt consumed before networking, reconciles
interrupted and already-complete candidates after restart, and permits exactly
one separately budgeted local retry only when acceptance remains unchanged. A
fresh signed two-install gate killed the requester after an authenticated peer
received the full request and sent zero response bytes. The restarted installed
service selected local `qwen3:1.7b`, returned `READY`, passed the same signed
verifier, exposed matching content-free recovery evidence, retained no prompt or
disclosure receipt, diagnosed both installs healthy, and removed both. This
remains same-host evidence; Phase 21.7 still requires two physical machines. The
final Phase 18 verifier-binding gate passes from a fresh
signed installation for exact text, sandboxed Python tests, byte-bound retrieval
citations, symbolic and numerical mathematics, and media artifact text. Phase 19
remains complete with signed real-VS-Code summary, test, preview, edit,
deterministic verification, model-free undo evidence, and a signed bounded
owner-workspace implementation loop. Interactive installed
testing also recovered two application tasks that had been stranded after a
rejected VS Code observation, stopped unchanged Console snapshots from causing
overlapping SSE/poll renders, and proved a signed update and immediate Console
port restart. The Phase 22 factory then produced and retired a physically
promotable QLoRA specialist through a signed installed lifecycle. The final
source suite passes 1,396 tests with two declared hardware/environment skips,
all 286 generated schemas validate, and the focused strict type gate passes all
14 Phase 22 production and exit targets. Phase 21.7 and Phase 23 are not
complete.

## Status legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete with evidence
- `[!]` Blocked; the blocking condition must be documented in the latest handoff

Only one phase should normally be marked in progress. Parallel work is allowed only when component boundaries make it independent and the handoff identifies coordination points.

## Product boundary

FAM_OS is an OS intelligence service woven through the user's existing applications above Linux:

```text
User -> FAM Shell / CLI / application surfaces
                         |
                FAM Core services
                  /            \
       Application Fabric      Expert | Memory | Verification
                |                       |
 Existing applications      Hardware Scheduler
                  \            /
              FAM Supervisor
                    |
          Linux kernel and drivers
```

The first compatibility target is a Linux PC with 16 GiB RAM, SSD storage, and no required discrete GPU. That constrained target is a minimum-machine regression profile, not the default limit for stronger hosts.

The reference development workstation is the current Linux test PC: a 24-core Intel Core Ultra 9 285K, approximately 64 GiB RAM, an NVIDIA GeForce RTX 5080 with approximately 16 GiB VRAM, and a 2 TB NVMe SSD. Full-workstation tests must expose all of those resource tiers to FAM_OS while retaining explicit operating-system headroom. See `docs/architecture/HARDWARE_VALIDATION_PROFILES.md` and ADR 0011.

**Weaving invariant:** Existing applications are capability providers. Native semantic connectors are preferred, but useful integration must also work through OS/tool APIs, Linux accessibility, and a restricted screen/input fallback. MCP is a supported connector protocol at the semantic/tool boundary, not the internal Application Fabric and not a bypass around permission or verification policy. Observation never implies action authority. See `docs/architecture/APPLICATION_WEAVING.md`, `docs/architecture/MCP_APPLICATION_CONNECTOR.md`, ADR 0003, and ADR 0012.

**Architecture evidence:** `handoffs/0003-application-weaving-boundary.md` establishes the integration ladder; `handoffs/0011-full-hardware-and-mcp-plan.md` records the dual hardware profiles and MCP connector boundary.

---

## Phase 0 — Governance and project foundation

**Goal:** Establish the canonical project boundary before implementation continues.

- [x] 0.1 Create `FAM_OS/` as the canonical project root.
- [x] 0.2 Add nested implementation rules in `AGENTS.md`.
- [x] 0.3 Define the no-god-module component boundaries.
- [x] 0.4 Define append-only major-change handoffs and template.
- [x] 0.5 Define append-only architecture decision records.
- [x] 0.6 Create the initial historical handoff linking the RNF prototype evidence.

**Exit gate:** A new agent can locate the mission, rules, plan, structure, current evidence, and next step without reading the entire parent workspace.

**Evidence:** `handoffs/0001-project-foundation.md`

---

## Phase 1 — Controlled prototype migration

**Goal:** Move proven RNF behavior into modular FAM_OS boundaries without carrying forward prototype coupling.

- [x] 1.1 Inventory every prototype module, config, script, test, artifact, and public behavior.
- [x] 1.2 Create an explicit migration map from prototype files to FAM_OS components.
- [x] 1.3 Create package skeletons with local README ownership documents.
- [x] 1.4 Extract typed contracts before moving concrete Ollama or systemd logic.
- [x] 1.5 Move hardware profiling behind a Linux hardware adapter.
- [x] 1.6 Move Ollama calls behind an inference-runtime adapter.
- [x] 1.7 Move cgroup/systemd operations behind supervisor adapters.
- [x] 1.8 Move verifier behavior into the verification component.
- [x] 1.9 Move orchestration into small application use cases.
- [x] 1.10 Reproduce all existing tests and measured experiments from the new structure.
- [x] 1.11 Mark the parent prototype read-only after parity is established.

**Exit gate:** FAM_OS reproduces routing, constrained expert activation, policy comparison, and verified escalation without importing implementation modules from the parent prototype.

**Current evidence:** Phase 1.1 through 1.4 are recorded in `handoffs/0002-prototype-map-and-contract-foundation.md`; Phase 1.5 is recorded in `handoffs/0004-linux-hardware-discovery.md`; Phase 1.6 is recorded in `handoffs/0005-ollama-inference-adapter.md`; Phase 1.7 is recorded in `handoffs/0006-systemd-cgroup-supervisor-adapters.md`; Phase 1.8 is recorded in `handoffs/0007-python-verifier-sandbox.md`; Phase 1.9 is recorded in `handoffs/0008-verified-code-orchestration.md`; measured Phase 1.10 parity is recorded in `handoffs/0009-phase1-measured-parity.md`; the Phase 1.11 prototype freeze is recorded in `handoffs/0010-parent-prototype-read-only.md`.

---

## Phase 2 — Contracts, schemas, and configuration foundation

**Goal:** Make every runtime boundary explicit and versioned.

**First application vertical slice:** The provider-neutral contracts are exercised with a VS Code-shaped fake connector before a real extension exists. The slice observes workspace/editor/document/selection state, prepares a reversible workspace edit, requires scoped permission and confirmation, executes through a connector port, and accepts success only after deterministic postcondition evidence. VS Code API and MCP wire types remain adapter concerns.

- [x] 2.1 Define request, route, capability, execution-plan, and final-result contracts.
- [x] 2.2 Define hardware-profile and resource-budget schemas, including host inventory, effective limits, reserved headroom, GPU VRAM, CPU allocation, and SSD/cache budgets.
- [x] 2.3 Define expert, verifier, connector, and memory-record manifests without binding the domain to one connector protocol.
- [x] 2.4 Define application identity, capability, observation, action, and action-result contracts.
- [x] 2.5 Define permission-grant, confirmation, reversibility, and postcondition contracts.
- [x] 2.6 Define structured error and degradation contracts.
- [x] 2.7 Add schema validation and compatibility tests.
- [x] 2.8 Define configuration layering: safe defaults, discovered hardware, named validation profile, user policy, and session overrides.
- [x] 2.9 Define connector transport metadata and the MCP-to-Application-Capability mapping.
- [x] 2.10 Create ADRs for every public schema and compatibility policy.
- [x] 2.11 Create versioned `compat-cpu-16gb` and `full-reference-workstation` validation profiles from the new schemas.
- [x] 2.12 Generalize benchmark service composition so the same workloads can run in constrained CPU-only or full-workstation GPU-enabled mode without duplicated orchestration.
- [x] 2.13 Capture a privacy-reviewed workstation profile and run a full-capability smoke baseline recording verified quality, CPU, RAM, VRAM, model transfers, SSD I/O, latency, and failures.
- [x] 2.14 Remediate the failed quality baseline with strict requirement-conformance checks, bounded verifier-owned repair context, decomposed examples, and independent full-workstation runs of the installed Laguna 33.4B Q4 and Gemma 4 25.8B Q4 experts.

**Exit gate:** Core and Application Fabric policy can be tested using in-memory experts, applications, verifiers, and hardware fakes without Ollama, systemd, desktop control, or hardware commands. Both named validation profiles pass schema and composition tests, and the reference workstation has a raw full-capability smoke artifact distinct from the 16 GiB CPU baseline.

**Current Phase 2 evidence:** Core request/routing/plan/result contract families for step 2.1 are recorded in `handoffs/0013-core-execution-plan-contracts.md`, `docs/protocols/CORE_CONTRACTS.md`, and ADR 0014. Versioned host-inventory and effective-resource-budget contract families for step 2.2 are recorded in `handoffs/0014-hardware-resource-contracts.md`, `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md`, and ADR 0015. Expert, verifier, connector, and memory-record manifests for step 2.3 are recorded in `handoffs/0015-component-manifest-contracts.md`, `docs/protocols/MANIFEST_CONTRACTS.md`, and ADR 0016. Python Application Fabric contracts, the VS Code-shaped fake connector, and transport/registry ports for steps 2.4, 2.5, and 2.9 are recorded in `handoffs/0012-application-fabric-contracts.md`, `docs/protocols/APPLICATION_CONTRACTS.md`, and ADR 0013. Structured failures, application failure evidence, explicit degradation, and safe final-result mapping for step 2.6 are recorded in `handoffs/0016-structured-failures-degradation.md`, `docs/protocols/FAILURE_DEGRADATION_CONTRACTS.md`, and ADR 0017. The first 27 strict serialized roots, exact alpha compatibility, fixed fixtures, cross-contract validation, and the public-schema ADR audit for steps 2.7 and 2.10 are recorded in `handoffs/0017-strict-schema-compatibility.md`, `docs/protocols/SERIALIZED_SCHEMA_COMPATIBILITY.md`, and ADR 0018. Deterministic defaults/profile/discovery/user/session composition, monotonic restriction policy, ordered audit decisions, and seven additional strict configuration roots for step 2.8 are recorded in `handoffs/0018-configuration-layering.md`, `docs/protocols/CONFIGURATION_LAYERING.md`, and ADR 0019. Concrete strict-schema minimum/full profile documents, a separate service envelope, and separation of reusable policy from captured machine state for step 2.11 are recorded in `handoffs/0019-dual-validation-profiles.md`, `docs/protocols/VALIDATION_PROFILE_DOCUMENTS.md`, and ADR 0020. Unified profile/budget admission, one Ollama/systemd service path, shared workload entrypoints, and profile-derived placement/report constraints for step 2.12 are recorded in `handoffs/0020-profile-driven-benchmark-composition.md`, `docs/operations/PROFILED_BENCHMARKS.md`, and ADR 0021. Privacy-reviewed live discovery, strict full-budget composition, expanded CPU/I/O/VRAM/model telemetry, and the canonical raw full-workstation baseline for step 2.13 are recorded in `handoffs/0021-full-workstation-smoke-baseline.md`, `docs/operations/FULL_WORKSTATION_SMOKE.md`, and ADR 0022. The original baseline remains an immutable failed-quality result with safe withholding. Strict conformance, explicit test disclosure to repair only, decomposed examples, and successful independent Laguna/Gemma full-workstation evidence for step 2.14 are recorded in `handoffs/0026-strong-model-quality-rerun.md`, the same operations guide, and ADR 0027. At the Phase 2 boundary a concrete authenticated local transport was not yet implemented; Phase 5 later supplied the peer-authenticated Unix Shell and Application Fabric transports.

---

## Phase 3 — FAM Supervisor

**Goal:** Create the smallest deterministic privileged boundary.

- [x] 3.1 Define supervisor capabilities and explicit non-goals.
- [x] 3.2 Implement unprivileged service lifecycle management.
- [x] 3.3 Implement cgroup CPU, memory, swap, and process budgets.
- [x] 3.4 Implement capability-based device and filesystem access.
- [x] 3.5 Implement immutable audit-event emission.
- [x] 3.6 Add failure recovery and safe service termination.
- [x] 3.7 Add supervisor threat model and security tests.

**Exit gate:** The supervisor can start, constrain, observe, and stop a dummy unprivileged service without containing model logic.

**Current Phase 3 evidence:** The canonical typed capability/non-goal boundary, current versus planned authority, user-session trust scope, and authenticated-caller assumptions for step 3.1 are recorded in `handoffs/0022-supervisor-boundary.md`, `docs/architecture/SUPERVISOR_BOUNDARY.md`, and ADR 0023. Authorization-injected principal/session ownership, independent `fam-` namespace restriction, exact-definition claims, idempotent lifecycle semantics, and a cleaned-up live user-service smoke for step 3.2 are recorded in `handoffs/0023-owned-service-lifecycle.md`, `docs/architecture/OWNED_SERVICE_LIFECYCLE.md`, and ADR 0024. Exact CPU/RAM/swap/task requested-versus-applied cgroup checks, explicit unbounded-versus-unavailable semantics, compensating stop, and a cleaned-up live constrained-service smoke for step 3.3 are recorded in `handoffs/0024-applied-resource-limits.md`, `docs/architecture/APPLIED_RESOURCE_LIMITS.md`, and ADR 0025. Opaque principal/session/service-scoped access grants, single-use revocation, provider-neutral allowlists, adapter-owned paths, and a live allowlist-only filesystem/device namespace proof for step 3.4 are recorded in `handoffs/0025-capability-access-grants.md`, `docs/architecture/CAPABILITY_ACCESS_GRANTS.md`, and ADR 0026. Required privacy-bounded request/outcome records, exact operation linkage, canonical JSONL encoding, private locked append, SHA-256 chain verification, duplicate-event rejection, compensation, and a live audited-service proof for step 3.5 are recorded in `handoffs/0027-immutable-supervisor-audit.md`, `docs/architecture/IMMUTABLE_SUPERVISOR_AUDIT.md`, and ADR 0028. Failed-to-inactive recovery, safe owned-service termination, deterministic grant retirement, systemd failed-state retention/reset, and a live exit-code failure cleanup proof for step 3.6 are recorded in `handoffs/0028-safe-service-recovery.md`, `docs/architecture/SAFE_SERVICE_RECOVERY.md`, and ADR 0029. The explicit attacker model, option/control/size/path hardening, bounded control-group termination, intelligence-import guard, adversarial tests, and combined live Phase 3 exit proof for step 3.7 are recorded in `handoffs/0029-supervisor-threat-model.md`, `docs/security/SUPERVISOR_THREAT_MODEL.md`, and ADR 0030. The external authentication transport, durable registries, trusted external audit-head checkpoint, and approved-command digest binding remained future work at this boundary. The Phase 23 audit has since added the signed `fam-os-userns` profile, narrow transient-verifier application, and installed host-security diagnosis without weakening the main service.

---

## Phase 4 — FAM Core request lifecycle

**Goal:** Implement a runtime-independent intelligence coordinator.

- [x] 4.1 Implement request admission and permission context.
- [x] 4.2 Implement FAM Core routing lifecycle.
- [x] 4.3 Implement execution-plan state machine.
- [x] 4.4 Implement authorized observation acquisition and action-proposal states.
- [x] 4.5 Implement approval, denial, and permission-expiry transitions.
- [x] 4.6 Implement bounded repair and escalation state transitions.
- [x] 4.7 Implement cancellation, timeout, and degradation paths.
- [x] 4.8 Implement final-result policy that withholds unverified outputs and failed actions.
- [x] 4.9 Add deterministic state-machine tests.
- [x] 4.10 Enforce an action-intent firewall before model selection so unresolved machine actions fail closed.
- [x] 4.11 Separate conversation answers, grounded answers, action proposals, verified action receipts, and unavailable capabilities in strict result contracts.

**Exit gate:** The full lifecycle passes against fake experts, applications, and verifiers with no inference runtime or desktop automation.

**Current Phase 4 evidence:** Steps 4.1-4.6 are recorded in handoffs 0030-0035 and ADRs 0031-0036 with their linked protocol documents. Replay-safe cancellation, trusted-deadline timeout, typed degradation, and absorbing terminal controls for step 4.7 are recorded in `handoffs/0036-core-control-transitions.md`, `docs/protocols/CORE_CONTROL_TRANSITIONS.md`, and ADR 0037. Registry-backed terminal release, candidate-linked passing acceptance, blocking degradation, and content-free non-release policy for step 4.8 are recorded in `handoffs/0037-core-final-result-policy.md`, `docs/protocols/CORE_FINAL_RESULT_POLICY.md`, and ADR 0038. The admission-to-terminal fake-driven matrix for verified release, denial, expiry, cancellation, timeout, degradation, attempt exhaustion, replay, and failed-content withholding for step 4.9 is recorded in `handoffs/0038-core-lifecycle-matrix.md` and `tests/integration/test_core_lifecycle_end_to_end.py`.

Corrective steps 4.10-4.11 close a later production integration gap that the
original Phase 4 fake matrix did not exercise: action-shaped natural language
could bypass capability resolution and enter conversation inference. The Core
now fails closed before model selection, permits action receipts only after
verified capability execution, and publishes explicit side-by-side
`v1alpha2` result/snapshot roots while preserving the exact `v1alpha1` schemas.
See ADR 0147, `docs/protocols/ACTION_INTENT_FIREWALL.md`, and handoff 0170.

---

## Phase 5 — Universal Application Fabric and FAM Shell

**Goal:** Make existing Linux applications usable as permissioned AI capabilities instead of requiring every application to become a custom plugin.

- [x] 5.1 Implement the dynamic Application Capability Registry.
- [x] 5.2 Implement the authenticated local intent, observation, action, and event transport.
- [x] 5.3 Implement an MCP client adapter that maps approved server tools and resources into Application Fabric capabilities.
- [x] 5.4 Expose an authenticated, permission-filtered local MCP server so compatible applications can request FAM capabilities without bypassing Core.
- [x] 5.5 Implement Linux application, process, window, focus, and launch discovery adapters.
- [x] 5.6 Implement deterministic file, MIME, desktop-portal, D-Bus, and tool capability adapters.
- [x] 5.7 Implement a Linux accessibility observation and action bridge.
- [x] 5.8 Build the FAM Shell MVP for Ask, context, plans, progress, approvals, cancellation, and results.
- [x] 5.9 Build one native code-editor semantic connector and SDK reference, using MCP where it preserves the required semantics.
- [x] 5.10 Define and constrain the screen-observation and input fallback adapter.
- [x] 5.11 Implement preconditions, postconditions, confirmation, undo/compensation metadata, and audit events.
- [x] 5.12 Run a cross-application acceptance demonstration and measure context, reliability, and resource cost by integration level.
- [x] 5.13 Add an owner-scoped create-directory capability with exact preview, approval, deterministic postcondition, content-free audit, and identity-bound empty-directory reversal.

**Current Phase 5 evidence:** Steps 5.1-5.5 are recorded in handoffs 0039-0043 and ADRs 0039-0043 with their linked protocol documents. Bounded shell-free process execution, scoped hash/precondition-bound atomic files, MIME provenance, exact primitive D-Bus calls, prepared portal URIs, allowlisted tool mappings, OS-tool registration, and live-safe reference probes for step 5.6 are recorded in `handoffs/0044-deterministic-linux-capabilities.md`, `docs/protocols/DETERMINISTIC_LINUX_CAPABILITIES.md`, and ADR 0044. Provider-isolated AT-SPI discovery, bounded opt-in-text observations, password-content redaction, fingerprinted stale-object rejection, allowlisted two-stage actions, explicit unavailability, and a mutation-free live desktop probe for step 5.7 are recorded in `handoffs/0045-linux-accessibility-bridge.md`, `docs/protocols/LINUX_ACCESSIBILITY_BRIDGE.md`, and ADR 0045. The unprivileged color-free `fam-shell` terminal, versioned Ask/context/plan/progress/approval/cancellation/result contracts, Core-side lifecycle projection, monotonic presentation reducer, terminal-control neutralization, and peer-authenticated bounded Unix transport for step 5.8 are recorded in `handoffs/0046-fam-shell-mvp.md`, `docs/protocols/FAM_SHELL_MVP.md`, and ADR 0046. The off-by-default VS Code extension, provider-neutral TypeScript connector SDK, bounded semantic observations, exact revision-bound reversible workspace edits, correlated native transport handshake, connector-owned schemas, and cross-language interoperability proof for step 5.9 are recorded in `handoffs/0047-native-vscode-semantic-connector.md`, `docs/protocols/VSCODE_SEMANTIC_CONNECTOR.md`, and ADR 0047. The exact active-window screen contract, independent capture/input availability, bounded PNG provider, allowlisted XTest primitives, exact-scene revalidation, explicit Wayland degradation, and non-mutating live X11 metadata proof for step 5.10 are recorded in `handoffs/0048-restricted-screen-input-fallback.md`, `docs/protocols/RESTRICTED_SCREEN_INPUT_FALLBACK.md`, and ADR 0048. Exact request/plan/capability/grant/proposal/approval binding, trusted pre/postcondition verification, atomic execution replay prevention, content-free required action audit, safe output withholding, and explicit recovery metadata for step 5.11 are recorded in `handoffs/0049-required-application-action-safety.md`, `docs/protocols/APPLICATION_ACTION_SAFETY.md`, and ADR 0049. The authenticated Shell vertical run through bounded AT-SPI, official-SDK MCP, deterministic file/test adapters, a local Ollama expert, the real isolated VS Code extension, approved verified edit, durable audit, integration-level reliability/resource measurements, and MCP-unavailable success for step 5.12 is recorded in `handoffs/0050-cross-application-acceptance.md`, `docs/operations/CROSS_APPLICATION_ACCEPTANCE.md`, ADR 0050, and `artifacts/application_fabric/phase5_acceptance.json`.

Step 5.13 is the first generic natural-language filesystem mutation admitted by
the corrective firewall. Tests prove missing-path follow-up, denial without
mutation, owner-root confinement, no-symlink traversal, verified creation,
privacy-bounded audit, and reversal only for the unchanged empty inode. No
model is invoked anywhere in that vertical path. See handoff 0170 and ADR 0147.

**Exit gate:** FAM Shell completes a verified cross-application task using one unmodified Linux application, one deterministic tool or OS capability, and one native semantic connector with explicit permissions and an auditable approval. The demonstration includes an MCP-backed capability but still succeeds at reduced fidelity when that MCP server is unavailable.

---

## Phase 6 — Expert Fabric registry and package system

**Goal:** Make experts installable, discoverable, compatible, and independently manageable.

- [x] 6.1 Finalize expert manifest schema and capability namespace.
- [x] 6.2 Implement local expert registry.
- [x] 6.3 Implement package validation, license metadata, signatures, and trust levels.
- [x] 6.4 Implement resource and hardware compatibility checks.
- [x] 6.5 Implement install, update, disable, rollback, and remove lifecycles.
- [x] 6.6 Implement routing embeddings and benchmark metadata, including initial-versus-repair outcome, disclosed verifier context, strict requirement-conformance failures, and full-host resource evidence.
- [x] 6.7 Add initial language, code, retrieval, and verifier package definitions; include escalation code packages for the already installed `laguna-xs.2:q4_K_M` and `gemma4:26b` models without making either the default tier.

**Current Phase 6 evidence:** The exact `fam.expert.capabilities/v1` namespace,
FAM-owned domains, publisher-bound extension branch, shared live/installable
validation, frozen `fam.expert.manifest/v1alpha1` decoding, finalized
`v1alpha2` schema, explicit migration, and version-owned schema rendering for
step 6.1 are recorded in `handoffs/0051-expert-manifest-capability-namespace.md`,
`docs/protocols/EXPERT_CAPABILITY_NAMESPACE.md`, and ADR 0051.
Atomic whole-catalog refresh, side-by-side package versions, exact
capability/tier/publisher indexes, immutable snapshots, revision events, and a
bounded strict local manifest source for step 6.2 are recorded in
`handoffs/0052-local-expert-registry.md`,
`docs/protocols/LOCAL_EXPERT_REGISTRY.md`, and ADR 0052.
Independent SHA-256 observation, exact SPDX-shaped license allow policy,
domain-separated canonical Ed25519 verification, configured publisher-key
revocation, exact built-in anchors, default-denied local packages, derived
effective trust, and three strict evidence/configuration roots for step 6.3 are
recorded in `handoffs/0053-package-trust-validation.md`,
`docs/protocols/PACKAGE_TRUST_VALIDATION.md`, and ADR 0053.
Profile-specific architecture, RAM, storage, accelerator, current-contention,
and optional CPU-fallback evaluation with a strict compatibility report for
step 6.4 are recorded in `handoffs/0054-expert-hardware-compatibility.md`,
`docs/protocols/EXPERT_HARDWARE_COMPATIBILITY.md`, and ADR 0054.
Durable revision-CAS installation state, immutable digest-checked artifact
staging, exact trust/compatibility admission, side-by-side known-good updates,
constrained-update retention, integrity-checked rollback, active-package removal
protection, and crash-recoverable deletion tombstones for step 6.5 are recorded
in `handoffs/0056-durable-expert-package-lifecycle.md`,
`docs/protocols/EXPERT_PACKAGE_LIFECYCLE.md`, and ADR 0055.
Exact-space normalized semantic embeddings, deterministic installed/capable
candidate ranking, immutable package-bound benchmark observations, explicit
initial/repair/escalation and verifier-disclosure evidence, strict conformance
failures, complete resource availability, raw-artifact digests, and the named
stable-toposort regression validator for step 6.6 are recorded in
`handoffs/0057-expert-routing-benchmark-metadata.md`,
`docs/protocols/EXPERT_ROUTING_BENCHMARK_METADATA.md`, and ADR 0056.
Exact installed-model runtime bindings, non-copying digest-reverified Ollama
artifact references, explicit local-development trust and license evidence,
language/code/retrieval/verifier definitions, declared-capability resolution,
side-by-side strong-package updates, real rollback/restore, adapter activation,
and independent full-workstation Laguna/Gemma regressions for step 6.7 are
recorded in `handoffs/0058-reference-expert-packages.md`,
`docs/protocols/REFERENCE_EXPERT_PACKAGES.md`, ADR 0057,
`artifacts/expert_fabric/phase6/`, and
`artifacts/workstation/20260716T170632701276Z/`.

**Exit gate:** An expert package can be installed, validated, selected by declared capability, activated through an adapter, and rolled back.

**Required strong-model regression:** Phase 6 cannot close using only small
experts. The initial package/benchmark set must rerun the immutable failed
stable-topological-sort baseline independently with both
`laguna-xs.2:q4_K_M` and `gemma4:26b` on the full-reference workstation. It
must preserve the strict input-order, neighbor-only, cycle, no-mutation, and
no-`set`/`min`/`sorted` requirements; disclose bounded trusted tests/examples
only to a repair step whose verifier policy permits disclosure; and retain
separate initial-attempt, repair, quality, RAM, VRAM, CPU, and storage evidence.
The historical successful reruns in handoff 0026 are evidence and a regression
floor, not a substitute for exercising the installed Phase 6 packages.

---

## Phase 7 — Hardware scheduler and neural pager

**Goal:** Schedule active intelligence across CPU, RAM, SSD, GPU, and NPU.

- [x] 7.1 Implement live cgroup-aware resource observation.
- [x] 7.2 Implement context-memory estimation.
- [x] 7.3 Implement cold, warm, active, and evicting expert states.
- [x] 7.4 Implement deterministic admission and eviction policy.
- [x] 7.5 Implement and retain the constrained CPU-only 16 GiB placement baseline.
- [x] 7.6 Implement full-workstation GPU placement, CPU/GPU split-offload, VRAM budgeting, and transfer-cost accounting.
- [x] 7.7 Implement SSD-backed model storage, memory-map/cache accounting, load/eviction telemetry, and explicit disk-I/O budgets; do not represent SSD as RAM.
- [x] 7.8 Investigate Intel NPU-compatible micro-experts.
- [x] 7.9 Implement cache telemetry and policy replay.
- [x] 7.10 Implement bounded predictive prefetching.

**Exit gate:** The scheduler keeps a multi-expert workload inside a real 16 GiB ceiling and, separately, uses the reference workstation's CPU, RAM, RTX VRAM, and NVMe tiers without artificial 16 GiB/CPU-only constraints. It explains every placement, context, transfer, and eviction decision and preserves an operating-system reserve in both profiles.

**Current Phase 7 evidence:** Repeated inclusive scope sampling, child-only
attribution, CPU counter deltas, lower-cgroup ceiling clamps, fail-closed unknown
GPU/cache capacity, bounded NVIDIA/cache adapters, the 52nd strict schema root,
and live baseline-to-complete captures for both named profiles in step 7.1 are
recorded in `handoffs/0059-live-scheduler-resource-observation.md`,
`docs/protocols/LIVE_SCHEDULER_RESOURCE_OBSERVATION.md`, ADR 0058, and
`artifacts/scheduler/phase7.1/`. The compatibility capture keeps GPU placement
disabled while the full-reference capture enables it; both use authoritative
cgroup memory, record a nonzero CPU delta, and clean up the transient service.
Strategy-specific model profiles, prompt/output/concurrency reservations,
auditable context-only estimates, autoregressive GQA KV arithmetic, encoder
quadratic attention bounds, strict Ollama metadata mapping, and live estimates
for all five current reference experts in step 7.2 are recorded in
`handoffs/0060-context-memory-estimation.md`,
`docs/protocols/CONTEXT_MEMORY_ESTIMATION.md`, ADR 0059, and
`artifacts/scheduler/phase7.2/reference-context-estimates/`. Laguna and Gemma are
both included; unknown Gemma KV topology is conservatively surfaced rather than
silently discounted.
Durable revision-bound cold/warm/active/evicting records, expiring request
leases, provider reconciliation, persist-before-unload eviction, ambiguity-safe
recovery, a private atomic filesystem repository, and a live isolated Qwen state
sequence in step 7.3 are recorded in
`handoffs/0061-durable-expert-residency.md`,
`docs/protocols/EXPERT_RESIDENCY_LIFECYCLE.md`, ADR 0060, and
`artifacts/scheduler/phase7.3/qwen-residency-lifecycle-canonical/`.
Strict weight-only admission inputs, separate context accounting, fail-closed
resource gates, warm-only stable eviction, and byte-stable decisions in step 7.4
are recorded in `handoffs/0062-deterministic-admission-and-eviction.md`,
`docs/protocols/DETERMINISTIC_ADMISSION_AND_EVICTION.md`, ADR 0061, and
`artifacts/scheduler/phase7.4/reference-admission-replay/`. The replay includes
all five downloaded experts: the full workstation admits Laguna and Gemma while
the honest 16 GiB compatibility ceiling rejects them without substituting a
weaker model.
The real constrained multi-expert execution in step 7.5 is recorded in
`handoffs/0063-constrained-cpu-only-baseline.md`,
`docs/protocols/CPU_ONLY_16GIB_BASELINE.md`, ADR 0062, and
`artifacts/scheduler/phase7.5/cpu-only-multi-expert-canonical/`. It applies an
exact 16 GiB service ceiling on the 64 GiB host without falsifying host capacity,
preserves a 2 GiB reserve, gives the workload 23 schedulable CPU cores, holds
Llama and Qwen resident together, records zero VRAM/swap/OOM, rejects Laguna and
Gemma before load, durably unloads both admitted experts, and leaves the isolated
service inactive.
Independent host/VRAM vector admission, exact accelerator-layer requests,
conservative mmap-safe host reservation, observed provider/NVIDIA placement, and
effective transfer-cost accounting in step 7.6 are recorded in
`handoffs/0064-full-workstation-gpu-placement.md`,
`docs/protocols/GPU_SPLIT_PLACEMENT.md`, ADR 0063, and
`artifacts/scheduler/phase7.6/full-gpu-placement-canonical/`. The isolated full
profile used 22 CPU cores and the RTX 5080, fully offloaded Llama/Qwen layers,
executed Laguna at 16/40 GPU layers and Gemma at 8/30, kept every observed VRAM
allocation inside its admitted bound, retained separate host compute bytes and
load/transfer costs, unloaded all models, and finished inactive.
Private digest-verified SSD artifacts, `mincore` mmap residency, safe owned-cache
eviction, cold/warm provider load telemetry, aggregate cgroup-process physical
and logical I/O, cumulative byte budgets, and optional exact systemd/cgroup
bandwidth enforcement in step 7.7 are recorded in
`handoffs/0065-ssd-model-paging.md`, `docs/protocols/SSD_MODEL_PAGING.md`, ADR
0064, and `artifacts/scheduler/phase7.7/llama-storage-paging-canonical/`. The
2.019 GB Llama artifact moved from fully cached to zero cached pages, the cold
load physically read 2.020 GB while the warm load read zero physical bytes, both
repopulated the full cache and unloaded, and SSD bytes are structurally excluded
from RAM capacity. This host's missing delegated `io.max` is recorded rather
than falsely claimed as kernel rate enforcement.
Physical Arrow Lake NPU discovery, strict host-versus-delegated access evidence,
a checksum-pinned isolated Intel 1.33/Level Zero 1.27/OpenVINO 2026.2 runtime,
and real NPU-only execution of a deterministic routing micro-expert in step 7.8
are recorded in `handoffs/0066-intel-npu-micro-expert.md`,
`docs/protocols/INTEL_NPU_MICRO_EXPERTS.md`, ADR 0065, and
`artifacts/scheduler/phase7.8/intel-npu-micro-expert-canonical/`. The compiled
model identified exactly `NPU` (`Intel(R) AI Boost`), selected the expected code
route, completed five warm trials, and recorded `fallback_used=false`. This is a
hardware/runtime feasibility proof; production NPU admission and benchmarked
micro-expert quality remain later Expert Fabric work.
Tier-separated cache observations, cold/warm/active invariants, deterministic
protected retention decisions, canonical document digests, and offline replay
of the real admission, GPU-placement, and cache policies in step 7.9 are
recorded in `handoffs/0067-cache-telemetry-policy-replay.md`,
`docs/protocols/CACHE_TELEMETRY_POLICY_REPLAY.md`, ADR 0066, and
`artifacts/scheduler/phase7.9/canonical-policy-replay/`. All 15 cases (ten host
admission, four GPU placement, and one cache retention) reproduce byte-for-byte
without consulting current host state. Page cache, provider weights,
accelerator weights, and NPU compiled state remain independent capacity tiers.
Digest-bound transition history, minimum evidence/confidence, prediction expiry,
independent byte/I/O/tier/reserve/concurrency/waste gates, zero eviction
authority, and an exact-range live Qwen page-cache prefetch in step 7.10 are
recorded in `handoffs/0068-bounded-predictive-prefetch.md`,
`docs/protocols/BOUNDED_PREDICTIVE_PREFETCH.md`, ADR 0067, and
`artifacts/scheduler/phase7.10/qwen-predictive-prefetch-canonical/`. Two prior
Llama-to-Qwen sequences produced confidence 1.0; the admitted 32 MiB prefetch
raised page-cache residency from zero, and the identical demand read required
zero physical disk I/O. A second speculation is rejected when it would exceed
the 64 MiB waste ceiling, and the owned temporary model clone is removed.

The Phase 23 implementation audit found that the installed request path did not
consume these resource and prefetch policies: production selection used only
`MemAvailable`, free NVIDIA memory, and a fixed reserve. The correction now
shares one live capacity projection between request selection and predictive
prewarming, preserves the named profile's host and VRAM reserves, applies the
managed Ollama cgroup remainder, and carries resource reasons into selection
and prewarm evidence. Missing managed cgroup evidence denies new cold host
allocation. This closes production reachability for observation and bounded
prefetch. See handoff 0172 and ADR 0148.

The following audit correction now composes Scheduler-owned residency into the
installed task worker and every auxiliary Ollama consumer. The first durable
catalog is built from provider evidence, process leases recover safely on
restart, generation and embedding hold leases through complete provider calls,
and managed Ollama may evict only provider-confirmed warm catalog models through
the existing persist-before-unload barrier. External Ollama remains explicitly
non-evictable. Predictive prewarming, document embeddings, remote execution,
synthetic teachers, and factory canaries share the same serialized provider
facade, with temporary canary models excluded from the eviction set. Focused
residency and product blast-radius suites passed in source. This closes the
source composition gap but is not fresh signed installed evidence. See handoff
0173 and ADR 0149.

---

## Phase 8 — Verification Fabric

**Goal:** Generalize verified execution beyond one code task.

- [x] 8.1 Finalize verifier manifest and trust model.
- [x] 8.2 Harden code sandboxing and document its security boundary.
- [x] 8.3 Add Python syntax, unit-test, type, and static-analysis verifiers.
- [x] 8.4 Add JavaScript/TypeScript and Rust verifier packages.
- [x] 8.5 Add mathematics symbolic and numerical verifiers.
- [x] 8.6 Add retrieval citation and provenance verifiers.
- [x] 8.7 Add application-action precondition and postcondition verifiers.
- [x] 8.8 Add global repair/escalation time and token budgets.

**Exit gate:** Multiple task families release results only when their declared acceptance policy passes.

**Current Phase 8 evidence:** Exact verifier package validation, verifier-specific
domain-separated signatures, immutable runtime artifact binding, minimum trust,
authority and schema allowlists, required isolation, fail-closed activation,
three strict schema roots, and real accepted/tampered activation evidence for
step 8.1 are recorded in `handoffs/0069-verifier-trust-activation.md`,
`docs/protocols/VERIFIER_TRUST_ACTIVATION.md`, ADR 0068, and
`artifacts/verification/phase8.1/verifier-trust-activation.json`.
Streaming fixed-cap output, process-group timeout termination, process rlimits,
minimal Bubblewrap environment, fail-closed namespace startup handling, an
explicit non-VM/non-seccomp boundary, and current-host hostile-probe evidence for
step 8.2 are recorded in `handoffs/0070-code-sandbox-hardening.md`,
`docs/security/CODE_SANDBOX_BOUNDARY.md`, ADR 0069, and
`artifacts/verification/phase8.2/sandbox-security-probe.json`. Corrected live
evidence uses a delegated systemd `TasksMax` scope around Bubblewrap and proves
home, network, system-write, environment, output, and timeout containment.
The conjunctive safe-syntax, sandbox-unit-test, strict-Mypy, and Ruff gates,
typed evidence schema, negative analyzer fixtures, and fully isolated live
result for step 8.3 are recorded in `handoffs/0071-python-quality-verifiers.md`,
`docs/protocols/PYTHON_QUALITY_VERIFIERS.md`, ADR 0070, and
`artifacts/verification/phase8.3/python-quality-verifiers.json`.
Real Node/TypeScript/rustc compiler and test gates, three local verifier package
manifests, a shared strict language-quality schema, default-denied direct
candidate execution, and positive/negative fixture evidence for step 8.4 are
recorded in `handoffs/0072-language-verifier-packages.md`,
`docs/protocols/LANGUAGE_VERIFIER_PACKAGES.md`, ADR 0071, and
`artifacts/verification/phase8.4/language-verifier-packages.json`.
Safe-AST SymPy symbolic equivalence, declared 80-digit numerical samples,
tolerance/error/counterexample evidence, two strict schemas, and identity/wrong
fixtures for step 8.5 are recorded in `handoffs/0073-math-verifiers.md`,
`docs/protocols/MATH_VERIFIERS.md`, ADR 0072, and
`artifacts/verification/phase8.5/math-verifiers.json`.
Exact full-source and quoted-span digests, provenance and locator binding,
all-claims release, a content-free strict report, and source-tamper evidence for
step 8.6 are recorded in `handoffs/0074-retrieval-citation-verifier.md`,
`docs/protocols/RETRIEVAL_CITATION_VERIFIER.md`, ADR 0073, and
`artifacts/verification/phase8.6/retrieval-verifier.json`.
Exact activated-verifier authority for application conditions, pre-mutation and
post-mutation Core verification, mandatory audit/output withholding, recovery
retention, and full integration tests for step 8.7 are recorded in
`handoffs/0075-application-condition-verifiers.md`,
`docs/protocols/APPLICATION_CONDITION_VERIFIERS.md`, and ADR 0074.
One atomic plan-global token/time ledger, separate repair/escalation counts,
non-refundable worst-case reservations, attempt replay protection, concurrency
tests, three strict schemas, and over-budget evidence for step 8.8 are recorded
in `handoffs/0076-global-attempt-budget.md`,
`docs/protocols/GLOBAL_ATTEMPT_BUDGET.md`, ADR 0075, and
`artifacts/verification/phase8.8/global-attempt-budget.json`.

**Phase 8 exit status:** Closed. Python, JavaScript/TypeScript, Rust, mathematics,
retrieval, and application-action families have declared conjunctive acceptance
evidence. Integration tests prove positive cases release only when all gates pass
and negative, tampered, unavailable-isolation, and over-budget cases are withheld.

---

## Phase 9 — Multi-task Expert Fabric

**Goal:** Expand the capability hierarchy using the smallest reliable models and tools.

- [x] 9.1 Build a benchmark covering kernel-only, code, math, retrieval, and application tasks, retaining the failed stable-topological-sort case as a named regression with independent Laguna and Gemma escalation-tier runs.
- [x] 9.2 Add micro-experts for routing, language detection, safety, and complexity.
- [x] 9.3 Add economical and escalation code tiers; prove that small-tier failures can escalate to the packaged Laguna and Gemma experts with bounded, policy-approved verifier feedback rather than silently weakening the task.
- [x] 9.4 Add retrieval embedding, reranking, and synthesis tiers.
- [x] 9.5 Add mathematics reasoning plus deterministic solvers.
- [x] 9.6 Add OCR, vision, speech recognition, and text-to-speech packages.
- [x] 9.7 Add quality-per-byte, quality-per-second, and quality-per-joule selection reports.
- [x] 9.8 Define evidence-based expert splitting, merging, and retirement rules.

**Exit gate:** FAM_OS completes a mixed verified benchmark and demonstrates that most tasks stop before the largest expert tier.

**Exit status:** Complete. `artifacts/expert_fabric/phase9-exit.json` records a
passing five-family benchmark with four of five tasks stopping before the
largest tier. Full validation and the eight-step evidence chain are recorded in
`handoffs/0086-phase9-capability-hierarchy-exit.md`.

**Current Phase 9 evidence:** The strict five-family suite, digest-bound fixtures,
exact acceptance linkage, kernel-without-model invariant, named stable-topological
regression, independent packaged Laguna/Gemma full-workstation runs, and passing
mixed report for step 9.1 are recorded in `handoffs/0078-mixed-verified-benchmark.md`,
`docs/protocols/MIXED_VERIFIED_BENCHMARK.md`, ADR 0077,
`configs/benchmarks/mixed-verified-v1.json`, and
`artifacts/expert_fabric/phase9.1/`.
Four authority-free micro-tier packages for routing, language detection, safety
screening, and complexity, exact runtime bindings, strict advice/benchmark
schemas, and fixture-bound classification evidence for step 9.2 are recorded in
`handoffs/0079-advisory-micro-experts.md`,
`docs/protocols/ADVISORY_MICRO_EXPERTS.md`, ADR 0078, and
`artifacts/expert_fabric/phase9.2/micro-expert-benchmark.json`.
Global pre-inference reservations, bounded/digest-bound verifier feedback, exact
unchanged acceptance, and live Qwen-7B-failure-to-Laguna/Gemma verified traces for
step 9.3 are recorded in `handoffs/0080-bounded-code-escalation.md`,
`docs/protocols/BOUNDED_CODE_ESCALATION.md`, ADR 0079, and
`artifacts/expert_fabric/phase9.3/`.
Provider-neutral batch embeddings, deterministic hybrid reranking, bounded cited
synthesis, separate package identities, independent exact-span release
verification, and a live Nomic/Llama workstation proof for step 9.4 are recorded
in `handoffs/0081-three-tier-retrieval.md`,
`docs/protocols/THREE_TIER_RETRIEVAL.md`, ADR 0080, and
`artifacts/expert_fabric/phase9.4/retrieval-tiers-workstation.json`.
Authority-free Llama reasoning, exact rational arithmetic, safe symbolic equation
solving, strict public schemas, and live solver-authoritative evidence for step 9.5 are recorded in
`handoffs/0082-verified-mathematics-experts.md`,
`docs/protocols/VERIFIED_MATHEMATICS_EXPERTS.md`, ADR 0081, and
`artifacts/expert_fabric/phase9.5/math-expert-workstation.json`.
Separately permissioned OCR, vision, English speech-recognition, and TTS
packages, explicit-file media ports, exact local artifact bindings, and passing
live Qwen3-VL plus Piper-to-Faster-Whisper evidence for step 9.6 are recorded in
`handoffs/0083-local-media-experts.md`,
`docs/protocols/LOCAL_MEDIA_EXPERTS.md`, ADR 0082, and
`artifacts/expert_fabric/phase9.6/media-expert-workstation.json`.
Independent quality-per-byte, quality-per-second, and quality-per-joule
selection, exact same-task measurements, raw NVIDIA power samples, and a strict
no-estimated-energy rule for step 9.7 are recorded in
`handoffs/0084-measured-expert-efficiency.md`,
`docs/protocols/EXPERT_EFFICIENCY_SELECTION.md`, ADR 0083, and
`artifacts/expert_fabric/phase9.7/expert-efficiency-workstation.json`.
Minimum-sample split, redundancy-based merge, quality-and-energy-dominant
retirement, and structurally unapplied approval-required proposals for step 9.8
are recorded in `handoffs/0085-evidence-based-expert-evolution.md`,
`docs/protocols/EVIDENCE_BASED_EXPERT_EVOLUTION.md`, ADR 0084, and
`artifacts/expert_fabric/phase9.8/expert-evolution-report.json`.

---

## Phase 10 — Memory and retrieval fabric

**Goal:** Add permissioned local knowledge without baking personal data into model weights.

- [x] 10.1 Define memory record, provenance, scope, expiry, and deletion schemas.
- [x] 10.2 Implement session and working memory.
- [x] 10.3 Implement approved document indexes and retrieval.
- [x] 10.4 Implement memory relevance gating.
- [x] 10.5 Implement inspection, correction, export, and deletion.
- [x] 10.6 Add encryption and multi-user isolation.
- [x] 10.7 Add retrieval-quality and privacy tests.

**Exit gate:** A user can inspect and delete every persistent memory item, and memory is retrieved only within its approved scope.

**Exit status:** Complete. The canonical evidence in
`artifacts/memory/phase10-exit.json` proves inspection and deletion with zero
remaining chunks, zero cross-scope hits, zero plaintext leaks, and 100% live
top-1 retrieval accuracy. Full validation is recorded in
`handoffs/0094-phase10-memory-fabric-exit.md`.

**Current Phase 10 evidence:** Existing strict record, provenance, owner/purpose/
application/workspace/session scope, sensitivity, retention, and expiry metadata,
plus deterministic expiry evaluation and removal-confirmed deletion request/
receipt schemas for step 10.1 are recorded in
`handoffs/0087-memory-lifecycle-contracts.md`,
`docs/protocols/MEMORY_RECORD_LIFECYCLE.md`, and ADR 0085.
Bounded digest-verified session/working storage, exact access contexts,
fail-closed capacity, expiry filtering/purge, and payload-first deletion for step
10.2 are recorded in `handoffs/0088-session-working-memory.md`,
`docs/protocols/SESSION_WORKING_MEMORY.md`, and ADR 0086.
Digest/scope/model-bound approvals, exact chunk reconstruction, durable SQLite
vectors, pre-scoring scope filtering, and live Nomic retrieval evidence for step
10.3 are recorded in `handoffs/0089-approved-document-indexes.md`,
`docs/protocols/APPROVED_DOCUMENT_INDEXES.md`, ADR 0087, and
`artifacts/memory/phase10.3/`.
Exact-scope-first freshness, relevance, and hard context-volume gates with stable
ordering and per-record rejection evidence for step 10.4 are recorded in
`handoffs/0090-memory-relevance-gating.md`,
`docs/protocols/MEMORY_RELEVANCE_GATING.md`, ADR 0088, and
`artifacts/memory/phase10.4/relevance-gate.json`.
Scope-authorized inspection, digest-verified export, atomic reindex correction,
cascading deletion, and live end-to-end management evidence for step 10.5 are
recorded in `handoffs/0091-memory-user-management.md`,
`docs/protocols/MEMORY_USER_MANAGEMENT.md`, ADR 0089, and
`artifacts/memory/phase10.5/`.
Owner-keyed AES-256-GCM content/vector encryption, authenticated owner binding,
plaintext-absence and cross-owner rejection evidence for step 10.6 are recorded
in `handoffs/0092-memory-encryption-isolation.md`,
`docs/protocols/MEMORY_ENCRYPTION_ISOLATION.md`, ADR 0090, and
`artifacts/memory/phase10.6/`.
Encrypted three-document live retrieval at 100% top-1 accuracy, zero cross-owner
hits, and zero raw-database plaintext leaks for step 10.7 are recorded in
`handoffs/0093-memory-quality-privacy.md`,
`docs/protocols/MEMORY_QUALITY_PRIVACY.md`, ADR 0091, and
`artifacts/memory/phase10.7/`.

---

## Phase 11 — Local adaptation and predictive behavior

**Goal:** Adapt scheduling and user experience without full-model training.

- [x] 11.1 Learn expert-frequency and cache predictions locally.
- [x] 11.2 Learn context and escalation predictions from verified outcomes.
- [x] 11.3 Add user preference adapters with inspection and reset.
- [x] 11.4 Add battery, thermal, foreground-load, and idle policies.
- [x] 11.5 Add rollback and drift detection.

**Exit gate:** Repeated workflows improve measured latency or energy without reducing verification quality or user control.

**Exit status:** Complete. `artifacts/adaptation/phase11-exit.json` records a
real repeated Qwen3 1.7B workflow improving from 1.014 seconds to 0.128 seconds
with identical verified quality and preserved preference reset control. See
`handoffs/0100-phase11-local-adaptation-exit.md`.

**Current Phase 11 evidence:** Local-only expert frequency with visible failure
counts plus the existing digest-bound, resource-admitted cache transition
predictor for step 11.1 are recorded in
`handoffs/0095-local-frequency-cache-learning.md`,
`docs/protocols/LOCAL_FREQUENCY_CACHE_LEARNING.md`, ADR 0092,
`artifacts/adaptation/phase11.1/`, and `artifacts/scheduler/phase7.10/`.
Digest-bound verified-only labels, conservative context prediction, and observed
escalation probability for step 11.2 are recorded in
`handoffs/0096-verified-outcome-prediction.md`,
`docs/protocols/VERIFIED_OUTCOME_PREDICTION.md`, ADR 0093, and
`artifacts/adaptation/phase11.2/`.
Closed normalized preference keys, owner-bound atomic storage, inspection,
cross-owner denial, and reset receipts for step 11.3 are recorded in
`handoffs/0097-user-preference-adapters.md`,
`docs/protocols/USER_PREFERENCE_ADAPTERS.md`, ADR 0094, and
`artifacts/adaptation/phase11.3/`.
Deterministic battery, thermal, foreground-load, and idle restrictions for step
11.4 are recorded in `handoffs/0098-operating-state-adaptation.md`,
`docs/protocols/OPERATING_STATE_ADAPTATION.md`, ADR 0095, and
`artifacts/adaptation/phase11.4/`.
The Phase 23 audit additionally proved the original policy had no installed
caller. Production now observes system battery state, the hottest valid sysfs
or NVIDIA temperature, normalized host load, and GNOME idle time at every
selection/prewarm boundary. Protective tier caps override residency and
escalation preferences; unknown thermal state disables speculation; and model
prewarming requires idle-background authority. See handoff 0172 and ADR 0148.
Immutable snapshots, verification/latency/energy drift, and exact-digest rollback
for step 11.5 are recorded in `handoffs/0099-adaptation-drift-rollback.md`,
`docs/protocols/ADAPTATION_DRIFT_ROLLBACK.md`, and ADR 0096.

---

## Phase 12 — Trusted multi-device fabric

**Goal:** Allow user-owned machines to contribute optional capacity securely.

- [x] 12.1 Define device identity and trust enrollment.
- [x] 12.2 Define remote expert capability and privacy policy.
- [x] 12.3 Implement encrypted authenticated transport.
- [x] 12.4 Implement latency-aware local-versus-remote scheduling.
- [x] 12.5 Implement disconnect and partial-failure recovery.
- [x] 12.6 Add desktop, laptop, and home-server demonstration.

**Exit gate:** A local task can use a trusted remote expert without exposing unauthorized context and can recover when the device disappears.

**Exit status:** Complete. The authenticated encrypted desktop/laptop/home-server
TCP demonstration selected the remote expert with zero unauthorized context,
verified its result, and preserved local acceptance after disconnect. Evidence is
in `artifacts/fabric/phase12/multidevice-demo.json` and
`handoffs/0106-phase12-trusted-fabric-exit.md`.

---

## Phase 13 — Expert Factory and hardware-aware training

**Goal:** Create and improve experts specifically for the fabric.

- [x] 13.1 Build failure-trace clustering and missing-capability discovery.
- [x] 13.2 Define teacher, distillation, adapter, and evaluation pipelines.
- [x] 13.3 Train routing and complexity micro-experts.
- [x] 13.4 Train or distill specialist experts with shared interfaces.
- [x] 13.5 Add activated-parameter, bytes-moved, latency, and energy costs to training objectives.
- [x] 13.6 Generate quantized variants and calibration metadata.
- [x] 13.7 Sign and publish expert packages.
- [x] 13.8 Add continuous benchmark and regression gates.

**Exit gate:** A new expert can be discovered from evidence, trained, packaged, installed, selected, verified, and retired through one auditable lifecycle.

**Exit status:** Complete. `artifacts/expert_factory/phase13/factory-lifecycle.json`
proves every lifecycle stage, including hardware objective, calibrated int4
variant, signed atomic publication, regression gate, and removal after retirement.
See `handoffs/0114-phase13-expert-factory-exit.md`.

---

## Phase 14 — Reliability, security, and productization

**Goal:** Turn the research runtime into a dependable OS service.

- [x] 14.1 Complete threat models and automated independent-tool security review.
- [x] 14.2 Add atomic updates and rollback for services, schemas, experts, and connectors.
- [x] 14.3 Add multi-user isolation and recovery mode.
- [x] 14.4 Add bounded thermal, storage, memory, and crash stress tests.
- [x] 14.5 Make FAM_OS trivial to install, update, diagnose, repair, and completely remove on Linux.
- [x] 14.6 Complete the production FAM Shell and Console for resources, experts, permissions, memory, audit history, and recovery.
- [x] 14.7 Publish reproducible minimum-hardware and full-reference-workstation benchmarks.

**Exit gate:** FAM_OS can be installed and removed safely, survives extended operation, and provides complete user visibility and control.

**Historical Phase 14 exit status:** Complete for its bounded component and
productization scope. The aggregate product gate reran safe installation,
damage diagnosis, repair, removal, signed atomic update and rollback, owner
isolation, recovery denials, and complete Console visibility. It binds the live
five-minute thermal/storage/memory/crash qualification and the profile-separated
reference benchmarks. It did not complete a human security review or a
long-running installed soak; those remain explicit Phase 23.7 and 23.5 gates.
Evidence is in `artifacts/product/phase14-exit.json` and
`handoffs/0122-phase14-product-exit.md`.

---

## Immediate next step

Implement Phase 21.7 by installing the same signed release on at least two
physical Linux machines, pairing them over a real network, and repeating remote
success plus requester/peer loss recovery under the exact Phase 21.1–21.6
contracts. Capture machine identity, network, hardware, service, budget,
privacy, verification, content-free evidence, removal, and no-unauthorized-
context proof from both hosts. Localhost, containers, VMs, and two prefixes on
one workstation do not satisfy this gate. Phase 22 local factory implementation
may proceed independently, but it cannot be used to claim Phase 21 or final
product completion and it must not consume a remote host as a substitute for
the missing physical qualification evidence.
A third-party human penetration test remains explicitly uncompleted and must
not be represented as certification.

**Final audit status:** In progress. Installed operational acceptance and
Phases 16–20 are complete, but the Master Plan remains incomplete until the open
steps in Phases 21–23 pass their installed exit gates.

---

## Phase 15 — Installed operational acceptance

**Goal:** Prove FAM_OS works as an installed, startable local AI product.

- [x] 15.1 Implement the production Core-to-inference Shell gateway.
- [x] 15.2 Implement the combined local service for Shell and Console.
- [x] 15.3 Correct generated Linux service configuration and lifecycle commands.
- [x] 15.4 Install into an isolated prefix and prove service startup and shutdown.
- [x] 15.5 Complete a real Shell request through Ollama and a downloaded model.
- [x] 15.6 Prove Console access against the same running service.
- [x] 15.7 Re-run update, diagnosis, repair, removal, regression, and soak gates.

**Exit gate:** A fresh installation starts one owner-scoped service, answers a
real local-model request from FAM Shell, serves authenticated Console state,
stops cleanly, detects and repairs damage, and removes every installed artifact.

**Exit status:** Complete. A fresh isolated installation executed its generated
service and Shell launchers, completed a real `qwen3:1.7b` request through
Ollama with measured GPU residency, served authenticated Console HTML and all
six state sections, shut down cleanly, detected damage, repaired, and removed
all artifacts. Six further real Shell and Console cycles passed a 60-second
operational soak with negligible RSS change. The full 842-test suite, 166
schemas, lint, typing, earlier Phase 14 exit, and fresh-venv wheel commands pass.
Evidence: `artifacts/product/phase15/phase15-exit.json` and
`handoffs/0126-phase15-installed-operational-exit.md`.

---

## Phase 16 — Rebaseline truth and integration ownership

**Goal:** Make component maturity and installed product maturity impossible to
confuse.

- [x] 16.1 Reclassify overall status without rewriting historical exits.
- [x] 16.2 Add the versioned integration coverage manifest and contract tests.
- [x] 16.3 Define final integration composition ownership and boundaries.
- [x] 16.4 Split and document clean dependency/test profiles.
- [x] 16.5 Prevent production composition from importing acceptance/evidence code.

**Exit gate:** Documentation and automated coverage checks report real maturity
without treating isolated artifacts as installed behavior.

**Exit status:** Complete. The 19-subsystem versioned manifest reports
integration incomplete, all 167 schemas validate, the 845-test base suite passes
with seven declared environment skips, and the production composition import
gate passes. See `handoffs/0127-final-integration-rebaseline.md`.

---

## Phase 17 — Durable production substrate and managed runtime

**Goal:** Make the installed service transactional, restart-safe, supervised,
and release-managed.

- [x] 17.1 Add owner-private SQLite WAL storage and ordered migrations.
- [x] 17.2 Add owner-bound encryption and fail-closed key recovery.
- [x] 17.3 Replace production volatile registries with transactional repositories.
- [x] 17.4 Reconcile inference, approvals, and uncertain actions after restart.
- [x] 17.5 Supervise managed Ollama, workers, cgroups, health, and model storage.
- [x] 17.6 Apply profile-derived CPU, RAM, process, and I/O-ready worker budgets while retaining Scheduler-owned VRAM placement.
- [x] 17.7 Ship signed complete release bundles with install/enable/update/repair/rollback/removal.

**Exit gate:** Restart during inference, approval, or action execution preserves
state without replaying mutation authority or losing evidence.

**Phase 17 exit evidence:** The signed seven-component offline release was
installed from its wheelhouse, started with encrypted migrated storage and a
managed cgroup-bounded Ollama, answered through the installed Shell, restarted,
served Console state, updated, rolled back, diagnosed, and removed. Durable
reconciliation tests prove approval loss and postcondition-only uncertain-action
recovery. Phase 18 subsequently replaced the fixed installed request path with
the unified durable Core. Broad installed release requalification remains a
Phase 23 gate rather than an unrecorded Phase 17 dependency.

The Phase 23 implementation audit later found that the action reconciler itself
had only test callers after the unified Core replacement. Production startup now
coordinates action, application, plan, and audit state before serving clients;
old approval is discarded, fresh recovery approval is bound to encrypted action
state, uncertain directory mutations are resolved only by independent
postcondition observation, and inconclusive actions visibly block without a
provider retry. This corrects production reachability for 17.4; the same flows
still require one-candidate installed evidence in 23.3. See handoff 0177 and ADR
0152.

---

## Phase 18 — Unified Core, Expert Fabric, scheduler, and verification

**Goal:** Route every installed request through one real, resource-aware,
verified lifecycle.

- [x] 18.1 Replace the fixed inference gateway with the production task gateway.
- [x] 18.2 Add policy-bound intent classification and plan compilation.
- [x] 18.3 Build a live signed expert/runtime catalog.
- [x] 18.4 Route economical, specialist, retrieval, media, and strong escalation models.
- [x] 18.5 Connect selection and residency to live host resources and Ollama state.
- [x] 18.6 Invoke declared verifiers and deterministic application postconditions.
- [x] 18.7 Add exact repair feedback, shared budgets, and non-weakening escalation.
- [x] 18.8 Label every result unverified, grounded, or verified.
- [x] 18.9 Route authority-bearing natural language through live capability resolution before ordinary inference.

**Exit gate:** A natural request traverses real Core, selects and escalates an
expert when needed, verifies acceptance, and leaves durable evidence.

**Current Phase 18 evidence:** The signed installed service routes natural
requests through durable admission, routing, immutable plans, a signed enabled
expert catalog, live resource/residency selection, background inference,
bounded repair/Laguna/Gemma escalation, structured assurance, and final-result
policy. An admitted request survived a full service stop before inference and
completed after restart. Exact-text, Python, retrieval, mathematics, and media
requests now carry typed declarations through Shell or Console, activate only
the exact signed package and runtime binding, execute the production verifier,
and persist candidate-bound run evidence. Python runs inside Bubblewrap,
retrieval claims bind authorized source bytes, mathematics uses safe-AST SymPy
plus declared numerical samples, and media binds the observed artifact bytes
and image-bearing inference request. Application and deterministic OS-tool
postconditions also run through Core and fail closed.

**Phase 18 exit status:** Complete. A fresh Ed25519-signed seven-component
release was installed privately and exercised all five declared verifier
domains through the installed Console, durable Core, production catalog, and
real verifier adapters. Every released result was `verified`, every verifier run
recorded `effective_trust: signed` with the exact release, signer, candidate,
acceptance contract, and verifier artifact digest, and the media request carried
its image bytes. Diagnosis and complete removal passed. See
`artifacts/verification/phase18-production-verifiers.json`, handoff 0142, and
ADR 0124.

Corrective step 18.9 makes intent classification authority-bearing rather than
advisory. Unsupported or incomplete actions now produce typed model-free
outcomes, while resolved actions compile through the same durable Application
Fabric plan and verification lifecycle. This correction is recorded in ADR
0147 and handoff 0170; it does not weaken any verifier or escalation policy.

The whole-plan corrective audit also found that model verifier declarations and
shared signed expert packages were not enforced as routing authority. Runtime
selection now requires the durable declaration's exact verifier across initial,
repair, escalation, fallback, and remote-recovery routes. Signed expert scopes
must exactly reconstruct each physical model's aggregate intents and verifiers;
enablement, peer declarations, persistence, and factory activation preserve
those scopes while residency still counts the shared weights once. The complete
1,365-test source suite passes. ADR 0158 and handoff 0181 record this correction;
the next signed installed candidate must repeat the Phase 18 profile evidence.

The same audit removed inferred package-version ordering and ambiguous JSON
authority. Every active expert scope now names its exact signed package
coordinate; side-by-side versions remain inactive unless selected explicitly.
All typed contract documents and the untyped runtime catalog reject duplicate
object keys instead of accepting JSON last-key-wins behavior. ADR 0159 and
handoff 0182 record this Phase 2/6/18 correction.

The archive follow-through now rejects duplicate, traversal, absolute, and
non-canonical signed expert members and requires each runtime expert scope to
reconstruct the selected package's verifier set exactly. The stale Nomic
verifier requirement was removed rather than invented in runtime configuration.
ADR 0160 and handoff 0183 record this signed-authority correction; the changes
are included in installed release `fam-os-workspace-20260718-02`.

---

## Phase 19 — Production application weaving and everyday UI

**Goal:** Make FAM_OS a usable workstation intelligence layer rather than a chat
frontend.

- [x] 19.1 Start and supervise the private Application Fabric endpoint.
- [x] 19.2 Compose capability registry, connector broker, discovery, adapters, and action safety.
- [x] 19.3 Package, install, discover, update, and remove the VS Code connector.
- [x] 19.4 Compile capability-driven plans instead of fixed acceptance prompts.
- [x] 19.5 Implement VS Code observe/diagnose/preview/apply/undo/save with disk verification.
- [x] 19.6 Compose allowlisted MCP client and permission-filtered ingress lifecycles.
- [x] 19.7 Keep accessibility and screen/input fallbacks explicit and off by default.
- [x] 19.8 Add durable task, event-stream, decision, and cancellation APIs.
- [x] 19.9 Replace bootstrap-token use with secure Console session and CSRF controls.
- [x] 19.10 Build the Console fabric execution spine and natural streaming Shell.
- [x] 19.11 Present answer, proposal, unavailable, and verified-receipt semantics truthfully in Console and Shell.
- [x] 19.12 Add explicit owner-local workspace selection, bounded folder/file observation, and a receipt-backed Tool terminal.
- [x] 19.13 Add a Core-owned bounded multi-step workspace tool loop for recursive discovery, retrieval, deterministic tools, and re-observation.
- [x] 19.14 Bind the authenticated Console launcher to the active installation runtime and detach the desktop handoff.
- [x] 19.15 Repair invalid workspace proposals with exact feedback, escalate once to a stronger expert, and expose bounded-scope failures honestly.

**Exit gate:** Console or Shell summarizes a project, runs a test, and performs
an approved VS Code edit with preview, undo, and deterministic verification.

**Current Phase 19 evidence:** The product service owns an owner-private
Application Fabric socket and composes the live registry, broker, discovery,
action policy, configured MCP clients, and deterministic scoped file/fixed-tool
providers. Shell integration tests now summarize a real project file, run an
owner-allowlisted test command after approval, and withhold unsafe results.
Native application tests cover observation, preview, approval, independent
postconditions, cancellation, authority revocation, and durable action state.
The VS Code package exposes active editor, selection, diagnostics, apply, undo,
and save capabilities; the Core independently verifies persisted file hashes.
Its VSIX lifecycle and exact `fam-os connector ... vscode` commands are tested.
The Console now exposes authenticated durable task, SSE, decision, and cancel
APIs behind HttpOnly SameSite sessions, Origin validation, and CSRF, while plain
Shell text submits and follows tasks automatically. The focused Python slice
passes 31 tests, and the connector passes TypeScript checking, seven tests,
native transport integration, and ten schema validations.

Allowlisted outbound MCP clients and permission-filtered ingress are now both
production-wired. Ingress is daemon-owned, disabled without an owner-private
allowlist, uses one-time bootstrap credentials over a mode-0600 Unix socket,
rechecks durable authority on every discovery and call, preserves the MCP client
principal through Core, and exposes an official MCP SDK stdio bridge. The
verification-required tool withholds unverified model output.

Step 19.7 composes both desktop fallbacks behind a strict owner-private
`fallbacks.json` contract. Absence registers no capability; enabled mechanisms
require privacy acknowledgement and exact process/window targets; observation
does not imply action; unavailable screen input degrades to observation-only.
The Console Applications surface exposes scopes, primitives, confirmation, and
privacy impact. Core independently re-observes AT-SPI fingerprints and screen
scenes after action.

**Phase 19 exit status:** Complete. Core owns deterministic reversal as a normal
durable approval-bound application task, rejects concurrent consumption,
permits retry after cancellation, and releases no token. Console presents real
structured previews, strict resumable SSE, direct undo, and locally bundled
OFL-licensed fonts. A freshly built Ed25519-signed seven-component release was
installed privately, its signed VSIX loaded in an isolated real VS Code 1.114
profile, and the complete summary, unittest, preview, edit, deterministic
verification, and undo scenario passed. Diagnosis and total removal also
passed. The full repository now passes 935 tests with two declared skips; 39
architecture tests, affected Mypy profiles, Ruff, connector compilation, seven
connector tests, native transport integration, and ten connector schemas pass.
See `artifacts/product/phase19/phase19-exit.json`, handoff 0141, and ADR 0123.

Corrective step 19.11 removes the remaining presentation ambiguity found during
installed owner testing. Console and Shell now distinguish an unverified model
answer from a grounded answer, a non-executed action proposal, an unavailable
capability, and an independently verified action receipt. Terminal branches that
were not traversed render as `not taken`, and only a verified action receipt may
expose reversal. See handoff 0170, ADR 0147, and
`artifacts/product/phase23/action-intent-firewall.json`.

Corrective step 19.12 closes the installed usability gap exposed when the model
printed an `ls` command without executing anything. Console now has an
authenticated owner-home folder picker, explicit selected-resource authority,
bounded `os.directory.list` and `os.file.read` observations, and a left-side
Tool terminal containing only Core observations, proposals, action results, and
receipt identifiers. Exact folder-list questions bypass model synthesis, while
analysis questions can still use experts over observed evidence. Signed release
`fam-os-workspace-20260718-02` was installed and returned the exact FAM_OS
top-level listing with two real observation receipts and no model invocation.
The complete source suite passes 1,383 tests with two declared skips. See ADR
0161, handoff 0184, `docs/operations/WORKSPACE_TOOL_TERMINAL.md`, and
`artifacts/product/phase19/workspace-tools-20260718.json`.

Corrective step 19.13 turns a selected owner workspace into a bounded repository
workflow without granting a raw terminal. Core now owns symlink-safe recursive
mapping, relevant UTF-8 retrieval, exact observation-hash binding, typed
existing-file patch proposals, unified-diff preview, owner approval, atomic
writes, re-observation, independent postconditions, and exact-byte reversal.
Prior session memory, authorized observations, and the current request are
separate inference messages, with the current request always last. A signed
installed release proved that a second request does not repeat the first, that
no file changes before approval, that an approved edit is independently
verified, and that authenticated Console undo restores the original hash.
The complete source suite passes 1,392 tests with two declared skips. See ADR
0162, handoff 0185, `docs/operations/WORKSPACE_TOOL_LOOP.md`, and
`artifacts/product/phase19/workspace-tool-loop-20260718.json`.

Corrective step 19.14 fixes the installed Console launch failure found in owner
testing. When `--runtime-root` is omitted, `fam-os ... console` now derives the
private runtime directory from the installation prefix, so a
`fam-os-current` installation reads the same token as the
`fam-os-current.service` process. The `xdg-open` handoff is spawned in a
detached session and a still-running desktop launcher counts as a successful
handoff instead of being killed after ten seconds. Signed release
`fam-os-console-launch-20260718-21` was installed and the exact documented
command returned `opened: true` in under one second; the resulting token
exchange returned HTTP 200. The complete source suite passes 1,396 tests with
two declared skips. See ADR 0163, handoff 0186, and
`artifacts/product/phase19/console-launch-20260718.json`.

Corrective step 19.15 fixes the opaque `application.action.parameters_invalid`
failure exposed by an owner asking FAM to implement a broad generated plan.
Core now validates nonempty typed proposals, returns the exact structural error
and authorized observed paths to one budgeted repair attempt, then selects a
different strongest-fitting local expert for one budgeted escalation. The model
may explicitly report that a request needs capabilities outside the bounded
existing-file patch tool; Core converts that into a deterministic invalid-request
result and never releases model claims as action evidence. Both terminal paths
state that no action ran and tell the owner how to narrow the task. Gemma and
Laguna now explicitly declare mutation escalation scope in both canonical and
packaged catalogs, and progress remains revision-stable while Core changes the
hidden selection. Signed release `fam-os-workspace-repair-20260718-24` is active;
the complete source suite passes 1,405 tests with two declared skips. See ADR
0164, handoff 0187, and
`artifacts/product/phase19/workspace-proposal-repair-20260718.json`.

---

## Phase 20 — Memory, retrieval, and local adaptation

**Goal:** Add grounded, user-controlled continuity that improves verified work.

- [x] 20.1 Enable bounded ephemeral session memory by default.
- [x] 20.2 Add opt-in scoped document/folder indexing with expiry.
- [x] 20.3 Ground identity and project answers with exact local citations.
- [x] 20.4 Add inspect/correct/export/expire/delete controls and receipts.
- [x] 20.5 Learn only from verified outcomes and minimize raw prompt retention.
- [x] 20.6 Connect prefetch, context, frequency, and escalation prediction live.
- [x] 20.7 Add visible disable/reset/drift/rollback behavior.

**Exit gate:** Repeated work improves latency or resource use while persistent
records and learned behavior remain inspectable and removable.

**Current Phase 20 evidence:** Steps 20.1 through 20.6 are complete. The installed service now
composes process-only conversation memory for every terminal Shell lifetime,
authenticated Console session, and authenticated MCP session. It retains a
rolling exact-session window with hard record, byte, turn, context, and
eight-hour TTL bounds. Prior turns enter inference as explicitly untrusted
conversation and cannot supply authority, observations, citations, or
verification. A fresh signed seven-component installation proved same-session
recall, cross-session isolation, restart erasure, encrypted durable state with no
plaintext test nonce, healthy diagnosis, and complete removal. See
`artifacts/memory/phase20.1-session-memory.json`, handoff 0143, and ADR 0125.
Persistent indexes remain absent by default. Authenticated users can now grant
one bounded file/folder scope with explicit recursion, extensions, resource
limits, application/workspace purpose, and expiry. The main ProductDatabase
stores grants, approvals, chunks, content, and embeddings as owner-bound AEAD
ciphertext; descriptor-relative traversal rejects symlinks and unstable or
nonregular files. A fresh signed seven-component installation proved opt-in
denial, safe scoped indexing, cascade expiry, active-grant restart persistence,
no plaintext nonce, healthy diagnosis, and complete removal. See
`artifacts/memory/phase20.2-document-indexing.json`, handoff 0144, and ADR 0126.
Identity and project requests now enter one policy-owned grounding path. Signed
packaged identity and active owner/purpose/application/session/workspace-scoped
indexes become bounded untrusted evidence; missing authority fails closed. The
signed retrieval verifier accepts only answers exactly composed from claims with
exact source quotes, and terminal projection exposes typed digest-bound citations
in Shell, Console, and MCP. A fresh signed seven-component installation proved
no-source denial, package identity, project retrieval, cross-application source
isolation, exact citations, signed verifier evidence, restart persistence,
healthy diagnosis, and complete removal. See
`artifacts/memory/phase20.3-grounded-answers.json`, handoff 0145, and ADR 0127.
The Phase 23 audit later found that exact citation bytes alone did not prove that
the cited answer addressed the question. Current declarations now bind the exact
query digest and deterministic lexical obligation; authorized sources and exact
cited spans must cover every obligation term, claim text must equal source text,
and legacy query-unbound declarations cannot newly pass. This is an extractive
relevance contract, not semantic completeness. Signed installed release
`fam-os-query-bound-20260718-02` verified the exact packaged identity answer and
withheld the prior unrelated residency-readiness prompt before inference. See
handoff 0174 and ADR 0150.
Persistent memory management is now owner-reachable through both authenticated
FAM Console and peer-authenticated FAM Shell. Owner authority is independent of
retrieval scope; inspect and export are read controls, while correction,
document deletion, and manual grant expiry require explicit confirmation and
durable request identity. Correction and deletion enforce current-content
digests. Every mutation and owner-encrypted receipt commits atomically, and
receipts survive payload and grant removal. A fresh signed seven-component
installation proved Shell and Console controls, missing-confirmation denial,
correction re-embedding, deletion, cascade and empty-grant expiry, encrypted
receipt persistence across restart, exact request replay, no plaintext test
nonce, healthy diagnosis, and complete removal. See
`artifacts/memory/phase20.4-memory-management.json`, handoff 0146, and ADR 0128.
Installed terminalization now retains the final presented result before
atomically normalizing durable working content. Only a verified release with one
passing acceptance-to-candidate binding creates an owner-encrypted learning
record; unverified, failed, denied, cancelled, and withheld outcomes create none.
The record contains only closed intent, expert, coarse context, escalation,
timestamp, and evidence metadata. Request/application prompt copies, all attempt
candidates, and verifier feedback are redacted and the declaration is removed,
while final results, citations, verifier facts/provenance, action results, and
undo remain. A fresh signed seven-component installation proved verified-only
learning, unverified exclusion, concurrent atomicity, restart result and record
persistence without inference replay, no plaintext test nonce, healthy
diagnosis, and complete removal. See
`artifacts/adaptation/phase20.5-verified-learning.json`, handoff 0147, and ADR
0129. Installed prediction now derives owner-encrypted content-free snapshots
from those verified records. Unique-leader frequency advises only same-tier
signed intent candidates; P95 context is bounded below by the complete active
prompt; escalation readiness uses a 0.75 threshold; and next-expert prewarm
requires two transitions at 0.75 confidence. Prompt-free Ollama preload is
resource-admitted with host reserve, requests no eviction, and requires observed
residency. A signed seven-component run proved two repair-to-Gemma escalations,
transition prewarm, a 32,768 to 2,048 repeated context reduction, unchanged
verified quality, encrypted restart reconstruction without inference replay, and
complete removal. A physical RTX 5080 run separately proved prompt-free load and
unload of downloaded `gemma4:26b` and `laguna-xs.2:q4_K_M`. See
`artifacts/adaptation/phase20.6-live-adaptation.json`,
`artifacts/adaptation/phase20.6-hardware-prewarm.json`, handoff 0148, and ADR
0130.

The Phase 20.7 source implementation now adds an owner-scoped durable control
state and receipt ledger, confirmed enable/disable/reset/evaluate/rollback
operations, encrypted inference and repeated health observations, explicit
unavailable dimensions, multi-dimensional drift reports, automatic restoration
of the known-good snapshot, and terminal-result-preserving reset semantics.
Peer-authenticated FAM Shell commands and authenticated/CSRF-protected Console
routes expose status, snapshots, prewarm receipts, health, drift, and control
receipts; the Console includes a resident-intelligence control panel. The
focused control, Shell transport, and Console suite passes, the changed modules
pass lint, and the complete source suite passes 1,004 tests with two declared
skips. Regression coverage proves that adaptation telemetry or terminal-observer
failure cannot fail inference or undo an already committed terminal result.

**Phase 20 exit status:** Complete. A fresh Ed25519-signed seven-component
installation proved Shell and Console inspection, two prompt-free prewarms, a
2,048-token adapted canary, a 32,768-token disabled request, healthy promotion,
repeated quality/latency/thermal/policy regression, automatic known-good
rollback, confirmation denial, disabled-state restart persistence, confirmed
manual rollback and reset, retention of ten terminal results, encrypted storage
without the plaintext test nonce, healthy diagnosis, and complete removal. See
`artifacts/adaptation/phase20.7-control-and-rollback.json`, handoff 0149, ADR
0131, and `docs/operations/PHASE20_ADAPTATION_CONTROLS.md`.

---

## Phase 21 — Real trusted multi-device fabric

**Goal:** Use optional user-owned physical machines without weakening privacy or
acceptance.

- [x] 21.1 Add supervised persistent peer identity, manual pairing, and mutual TLS.
- [x] 21.2 Persist enrollment, revocation, capability, performance, and privacy policy.
- [x] 21.3 Enforce minimum approved remote context.
- [x] 21.4 Integrate remote selection with Core, Scheduler, budgets, and verification.
- [x] 21.5 Bind complete remote evidence and discard partial output.
- [x] 21.6 Reconcile disconnects and unchanged-acceptance local retry.
- [~] 21.7 Qualify on at least two physical Linux machines.

**Exit gate:** A trusted physical peer executes a real task, survives peer loss,
and produces the same verified contract without unauthorized context.

**Current Phase 21 evidence:** Steps 21.1–21.2 are complete. The installed product now
creates a persistent owner-private Ed25519 device root, issues a separate
client/server TLS leaf, and fails closed rather than replacing partial or
tampered identity. Installed CLI commands configure the disabled-by-default
listener, exchange signed expiring offers, calculate a two-device comparison
code, require literal owner confirmation, and commit the signed approval into
encrypted revisioned enrollment storage. The supervised listener reconstructs
its active trust set after restart, accepts TLS 1.3 only, requires certificates
in both directions, post-binds the leaf to the paired device, bounds frames, and
currently accepts only typed health control messages. A fresh signed
seven-component release installed into two isolated prefixes proved the full
ceremony, missing-confirmation denial, encrypted peer metadata, private key
modes, authenticated health, stable server identity after restart, healthy
diagnosis, and complete removal. This is same-host installed evidence, not the
physical Phase 21.7 gate. See `artifacts/fabric/phase21.1-persistent-mtls.json`,
handoff 0150, and ADR 0132.

Phase 21.2 adds peer-root-signed declarations for the exact installed experts,
models, capabilities, manifest digests, context ceilings, and validity. The
requesting machine measures TLS round-trip locally; peer-reported performance is
not trusted. Migration 0017 encrypts capabilities, bounded performance history,
per-peer privacy policy, and replay-safe management receipts. The directory is
an active-enrollment-only projection and has no enrollment operation. Shell and
Console expose probe, privacy, receipt, and confirmed revision-bound revoke
controls. Revocation commits atomically, closes the listener before rebuilding
trust, rechecks active enrollment on every request, disappears from discovery,
and persists across restart. A fresh signed two-install exit declared all seven
installed models—including Laguna and Gemma—measured authenticated latency,
proved missing-confirmation denial, immediate and restart revocation, encrypted
sensitive labels, healthy diagnosis, and complete removal. It remains same-host
evidence. See `artifacts/fabric/phase21.2-peer-state-and-controls.json`, handoff
0151, ADR 0133, and the Console Devices workspace.

Phase 21.3 is complete. The tree contains the strict
`fam.fabric.minimum-context/v1alpha1` envelope, exact UTF-8 fragment digests,
Ed25519 context and receipt signing, content-free disclosure evidence, migration
0018 encrypted evidence storage, and authenticated receiver capability validation.
Raw content is represented only by the explicit prompt, file-excerpt, memory,
and retrieval fragment kinds and requires confirmation at the contract boundary.
Outbound transfer binds the exact encrypted policy revision and selected signed
capability declaration before opening a socket. Shell and Console expose transfer
and content-free evidence. A fresh signed two-install gate selected the installed
Gemma 4 26B expert, verified three peer-signed receipts, denied unapproved prompt,
file, memory, retrieval, purpose, workspace, sensitivity, and capability cases
without changing the receiver count, found no raw sentinel in either database or
evidence response, diagnosed both installs healthy, and removed both completely.
This remains same-host evidence and does not satisfy Phase 21.7. See
`artifacts/fabric/phase21.3-minimum-context.json`, handoff 0152, and ADR 0134.

Phase 21.4 is complete. The source route defines
an explicitly confirmed remote-execution authority and content-free route plan,
filters the active trusted-peer directory by exact privacy revision and scope,
requires a locally measured authenticated probe and matching peer-root-signed
capability, and lets the Fabric Scheduler select the eligible remote expert.
Core persists the selection in the normal inference record, reserves the remote
attempt in the same durable global budget, transfers only the Phase 21.3 approved
context, verifies the peer-signed bounded result and mutual-TLS identities, and
feeds the candidate through the existing verifier and final-result policy. A
rejected remote candidate may consume the remaining unchanged local repair path;
ordinary requests stay local unless explicit remote authority is present. Shell
and Console expose this authority and require confirmation. Focused source tests
cover successful remote execution, verifier-driven local repair, policy revision
revocation after admission, signature and identity tampering, missing
confirmation, and verified-outcome learning. A fresh signed seven-component
release installed twice selected downloaded `gemma4:26b`, reserved the remote
attempt in the durable global budget, received and verified the peer-signed
complete result, passed the signed exact-text verifier, and released `READY`. It
proved missing confirmation, stale revision, unapproved workspace, and excessive
context caused no request persistence or disclosure; an ordinary task had no
remote plan and no peer disclosure; evidence and both databases contained no
prompt; both installs diagnosed healthy and were removed. This remains same-host
evidence. See `artifacts/fabric/phase21.4-remote-core-route.json`, handoff 0153,
and ADR 0135.

Phase 21.5 is complete. The source tree defines the strict content-free
remote-execution evidence contract and atomically persists it with the candidate
after a complete authenticated exchange. The record binds the Core request,
remote plan and request/result digests, peer and expert identities, approved
context and peer-signed receipt, budget reservation, candidate, verifier outcome,
and final disposition. Final-result policy releases a remote candidate only when
that evidence is finalized consistently; rejected remote candidates are retained
as rejected audit evidence, and the Console task API exposes the owner-visible
record. Focused source tests cover successful verified release, verifier-driven
local repair, forged or unfinished evidence rejection, and a truncated transport
response that persists neither a candidate, remote evidence, nor partial bytes.
An authenticated Console task endpoint exposes the same content-free record.
A fresh signed two-install gate released real downloaded `gemma4:26b` output
with the finalized evidence, then served an actual truncated mutual-TLS frame:
40 of 72 declared bytes. Core failed safely with no candidate or evidence row,
no additional disclosure receipt, no sentinel in either SQLite database, and no
released content. The durable remote reservation remains visible while its
execution reconciliation flag remains pending for Phase 21.6. Both installs
diagnosed healthy and were completely removed. The full suite passes 1,047 tests
with two skips; Ruff, affected Mypy, all 239 schemas, contract tests, and diff
validation pass. See `artifacts/fabric/phase21.5-complete-remote-evidence.json`,
handoff 0154, and ADR 0136. This same-host evidence does not satisfy Phase 21.7.

Phase 21.6 is complete. Remote and local-recovery reservations bind the exact
immutable request, authority activity, plan, remote route, and verifier
declaration digest. Core persists remote-attempt consumption before opening the
socket, classifies disconnect, timeout, partial, uncertain, provider, policy,
authentication, and invalid-result states, and denies retry for changed or
untrusted acceptance. A retryable loss consumes one explicit `local_recovery`
reservation, selects a locally admissible model, creates content-free recovery
evidence, and feeds the new candidate through the unchanged verifier and final
policy. Restart reconciliation handles loss after reservation, after pending
recovery, after the authenticated remote-candidate transaction, and after the
recovered local-candidate transaction without repeating retained work. Console
exposes the recovery audit record. A fresh signed two-install gate authenticated
the desktop request at the peer, sent zero response bytes, killed the desktop
process, confirmed the interrupted encrypted state had only the bound remote
reservation, restarted the installed service, reserved exactly one local retry,
ran `qwen3:1.7b`, verified `READY` with the signed exact-text package, and
released it with matching recovery evidence. No prompt or context receipt was
retained; both installs diagnosed healthy and were completely removed. The full
suite passes 1,053 tests with two skips; Ruff, affected Mypy, all 240 schemas,
contracts, and diff validation pass. See
`artifacts/fabric/phase21.6-remote-loss-recovery.json`, handoff 0155, and ADR
0137. This same-host evidence does not satisfy Phase 21.7.

Phase 21.7 is in progress. The tree now contains strict content-free physical
host evidence, a generated schema, an installed-code probe that rejects
virtualized or loopback-only hosts, fail-closed distinct-host/release validation,
and the complete two-machine operating procedure in
`docs/operations/PHASE21_PHYSICAL_QUALIFICATION.md`. The current workstation
reports `systemd-detect-virt: none` and has non-loopback LAN connectivity, so it
can serve as the requester. The required second physical Linux host, its signed
installation, and the resulting cross-host success/loss artifact are not present;
step 21.7 therefore remains open.

The Phase 21.7 qualification kit is recorded in handoff 0156 and ADR 0138. The
current source baseline passes 1,064 tests with two declared skips, all 242
generated schemas validate, and the installed-code physical-host contract and
fail-closed two-host report validator have focused coverage. This preparation
is not cross-host operational evidence and does not change the step status.

---

## Phase 22 — Real Expert Factory

**Goal:** Produce governed LoRA/QLoRA specialists from verified local failures.

- [x] 22.1 Supervise failure discovery and automated generation of provenance-bound synthetic training sets.
- [x] 22.2 Require approval of capability, data, model, license, budget, and runtime.
- [x] 22.3 Implement an isolated PyTorch/TRL/PEFT/bitsandbytes training backend.
- [x] 22.4 Build immutable training sets with verifiable lineage, automatic deduplication, and leakage controls.
- [x] 22.5 Schedule training only under approved safe resource conditions.
- [x] 22.6 Evaluate quality, safety, latency, RAM, VRAM, and energy regression.
- [x] 22.7 Convert with pinned tooling, sign, package, install, and canary.
- [x] 22.8 Roll back and retire without deleting audit history.

**Exit gate:** An approved specialist improves held-out evidence, is selected by
FAM_OS, and can be rolled back and removed.

**Implementation plan:** `docs/architecture/PHASE22_REAL_EXPERT_FACTORY.md`
defines the production boundary, explicit training-data authority, split-before-
synthesis rule, empirical sample-size checkpoints, isolated QLoRA backend,
resource admission, multidimensional evaluation, signed activation, and audit-
preserving retirement. The former Phase 13 token classifier remains acceptance
evidence only and is not a Phase 22 training backend.

**Current Phase 22 evidence:** The architecture, data-volume policy, authority
boundaries, and production sequence are now explicit. Signed deterministic
verifier failures can enter a supervised product observer before terminal
redaction, become strict content-free traces with candidate and verifier
digests, form deterministic immutable cluster snapshots, and produce proposal-
only missing-capability records after repeated evidence. Migration 0019 stores
traces, clusters, and proposals as owner-encrypted append-only contracts; source
or unsigned verifier runs are ignored, observer failure cannot fail inference,
and neither trace nor proposal can authorize training. The normal Phase 20
terminal redaction remains unchanged.

The governed dataset half of 22.1 is now source-complete. Confirmed expiring
capture grants bind an existing proposal, capability, source kinds, workspace
scopes, sensitivities, byte count, example count, and revision without granting
training authority. Migration 0020 persists grants, revocations, captured
sources, synthetic proposals, and independent reviews under owner encryption.
A deterministic policy assigns each source family to train, validation, or
held-out before synthesis; descendants inherit that partition, and held-out
sources are rejected before a teacher call. The bounded local Ollama teacher
requires strict JSON, while a separate deterministic reviewer decides whether
each proposal may enter the accepted projection. Revocation, expiry, byte and
count bounds fail before content insertion. Authenticated Console APIs expose
content-free discovery plus confirmed capture, review, sealing, approval,
environment-probe, and training controls.

Steps 22.2–22.5 now have production source implementations and physical
workstation evidence. Migration 0021 persists one-use six-dimensional training
approvals and revocations. Migration 0022 stores leakage reports, immutable
sealed dataset manifests, and encrypted content-addressed partition receipts;
canonical train, validation, and held-out blobs are exact- and near-deduplicated,
cross-partition leakage is rejected, and the training workspace decrypts only
train and validation. Migrations 0023–0024 persist exact backend environments,
atomic approval consumption and training jobs, terminal receipts, resource
snapshots, and admission decisions. The environment identity binds the Python
executable, 77-wheel offline manifest, exact package versions, worker script,
CUDA/driver/GPU facts, and compatibility result. Resource admission fails closed
on CPU, RAM, disk, VRAM, thermal, foreground, or Ollama conflicts; the worker
runs in a systemd user scope and network-denied Bubblewrap namespace with cgroup
RAM/CPU/swap/wall limits and parent-observed VRAM, temperature, power, output,
checkpoint, and approval-revocation stops.

The official Apache-2.0 `Qwen/Qwen3-1.7B` revision
`70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` is locally pinned by the
`15798168…e5851b7e` file manifest. Physical smoke attempts 01–04 failed closed
and remain as diagnostic evidence; bounded structured frames exposed missing
offline cache, `/bin/sh`, and `/sbin/ldconfig` sandbox dependencies without
including training content. Attempt 05 completed a real one-step QLoRA job on
the RTX 5080. The accepted terminal receipt binds environment
`e3d0a5a7…dc085b0`, dataset `4630b66f…09e55c7`, and adapter
`3eb4fd1b…47ada79`; it independently proved a 28,918,060-byte adapter, frozen
base weights, no unexpected trainable parameter, network denial, held-out
absence, 1,869,381,632 peak RAM bytes, 5,475,663,872 peak VRAM bytes, 45 °C
maximum temperature, and 664 measured joules. Parent-side validation recomputed
the adapter, adapter-config, metrics, and size rather than trusting the worker.
See `artifacts/training/phase22-physical-smoke-20260717-05/evidence.json`.

Phase 22.6 now has a production source implementation and a physical
non-promotable gate. Migration 0025 persists one-use evaluation approvals,
evaluator runs, held-out disposal receipts, ordered paired measurements,
reports, and Ed25519-signed comparison decisions under owner encryption. The
separate evaluator workspace decrypts only the held-out partition, runs the
frozen incumbent and adapter in one network-denied GPU sandbox, retains only
content hashes and measurements, removes plaintext before recording access,
and hard-gates quality confidence, safety, policy, unrelated regression,
latency, RAM, VRAM, energy, size, cold start, and scheduler compatibility.
The physical run evaluated the real smoke adapter against the exact Qwen3-1.7B
base over four cases. It measured baseline/candidate p95 latency of 2,297,789 /
3,028,036 microseconds, peak RAM of 5,132,132,352 / 5,889,531,904 bytes, peak
VRAM of 1,415,023,616 / 1,449,364,480 bytes, and energy of 445 / 653 joules.
The signed decision correctly denied promotion for insufficient samples, no
confident improvement, and safety/policy failures. A second scheduler-qualified
run removed the earlier scheduler-incompatibility reason while preserving the
correct non-promotable result;
341 held-out plaintext bytes were discarded and no held-out path remained.
See
`artifacts/training/phase22-physical-smoke-20260717-05/evaluation-evidence-phase22-physical-evaluation-scheduler-v2.json`
and handoff 0161. This proved the gate rather than specialist quality; the later
canonical chat-format checkpoint described below passed the same fixed gate.

Phase 22.7 was source-wired before a candidate was promotable. Primary-source review of LoRA,
QLoRA, LIMA, and the official PEFT/TRL training guides is recorded in the Phase
22 architecture plan; it confirms the frozen-base adapter mechanics and supports
measured learning curves rather than a universal sample-count claim. The product
service can now optionally compose the digest-pinned llama.cpp conversion
backend, signed disabled package installer, configured-suite canary, and separate
activation service. The owner facade and authenticated Console routes expose
confirmed environment probe, one-use conversion, packaging, canary, activation,
and durable evidence queries. Focused source tests prove the former unreachable
composition no longer fails on slotted settings, conversion reaches the concrete
backend, configured canary suites cannot be substituted, and encrypted evidence
collections survive restart. At that checkpoint no promotable adapter existed,
so conversion correctly remained denied. The canonical signed-installed exit
below now completes this boundary without reinterpreting those earlier denials.

The first governed specialist learning curve is now physical rather than a
sample-count assumption. Captured held-out records carry an encrypted, sealed
evaluation kind, verifier kind, and requirement identity; the evaluator rejects
incompatible kind/verifier combinations and supports deterministic Python,
exact-text, final-integer, safe-refusal, and evidence-honesty checks. Explicit
`quality256`, `balanced512`, `balanced1000`, and `balanced2500` plans bind their
partition quotas and derive optimizer steps from the sealed train count. The
1,000 and 2,500 checkpoints used the same pre-sealed 52-case suite
`21773b83…d2684` and the same 56-record held-out floor. The 1,000 run fixed all
policy cases and unrelated arithmetic but reached only 51.39% quality and had
one safety failure. The 2,500 quality-majority run reached 100% quality with a
94.93% lower confidence bound and no unrelated regression, but one safety and
one policy failure correctly denied promotion. Both signed decisions are
non-promotable, both discarded held-out plaintext, and neither may enter
conversion. Evidence is under
`artifacts/training/phase22-stable-toposort-balanced1000-20260718-01/` and
`artifacts/training/phase22-stable-toposort-balanced2500-20260718-01/`.
The 5,000 checkpoint retained 100% quality but still had one safety failure and
worsened from one to three policy failures. Scaling the same six policy and one
safety prompt shapes therefore saturated and is not a justification for the
10,000 checkpoint. A bounded Gemma 26B development-teacher probe independently
produced diverse refusal language and exposed both a narrow safety-verifier
vocabulary and low semantic diversity in the training generator. The separate
`diverse2500` plan preserved the same held-out records, used a 50/20/20/10
quality/safety/policy/unrelated mix, and broadened verified guardrail forms. It
still produced one safety failure, three policy failures, and only 33.3%
unrelated pass, so its signed decision is also non-promotable.

An independent non-held-out development probe then showed five of five safe
refusals, one unsupported success claim in five evidence-honesty prompts, and
correct arithmetic wrapped in prohibited prose. The QLoRA worker audit found a
more fundamental representation defect: the first physical series trained raw
string prompts, while installed inference and the evaluator use Qwen chat
messages with thinking disabled. The worker now requires the explicit
`qwen_chat_prompt_completion_v1` format, conversational user/assistant records,
`enable_thinking=false`, completion-only loss, and the tokenizer EOS. Its exact
script remains part of the training environment digest, so this correction
created new approval evidence rather than rewriting earlier jobs. The canonical
`diverse2500` repeat retained the fixed 52-case suite and 56-record held-out
floor. Run `phase22-stable-toposort-diverse2500-chat-20260718-03` verified all
2,868 governed fixtures, trained 2,500 records, kept the base frozen and held-out
partition absent, and produced adapter
`fba7c074…6c4695fa` under network denial. The signed comparison reached 100%
quality with a 94.93% lower confidence bound, zero safety failures, zero policy
failures, and 83.33% unrelated quality versus 33.33% for the incumbent. It was
therefore promotable with no reason codes. See ADR 0141 and
`artifacts/training/phase22-stable-toposort-diverse2500-chat-20260718-03/evidence.json`.

The first release attempts then failed closed and exposed real integration
defects rather than being bypassed: inconsistent local-owner namespaces, a
double-appended product state path, timestamp-bearing conversion identity,
unsupported transient-scope output properties, missing hermetic cache identity,
an intent/capability namespace mismatch, and an obsolete Ollama CLI JSON flag.
ADRs 0142–0146 record the durable corrections. Release attempt 10 executed from
the fresh seven-component Ed25519-signed installation, as proven by its installed
module path and digest. It converted a 2,165,039,328-byte Q8_0 base and
34,892,384-byte F16 adapter under network denial, signed and installed package
`fam.specialist.stable-toposort` disabled, selected only
`code.generate.python`, passed its declared Python canary, activated, manually
rolled back, reactivated, retired, removed the Ollama model and installed
artifact, and retained the encrypted audit history.

**Phase 22 exit status:** Complete. The aggregate content-free exit artifact
passes every physical, promotion, conversion, canary, activation, rollback,
retirement, installed-runtime, signed-install diagnosis, and complete-removal
check. It binds signed decision `192299eb…9c40f9`, sealed suite
`21773b83…d2684`, the exact training and release evidence hashes, and the signed
release manifest without retaining the ephemeral qualification key or held-out
plaintext. See
`artifacts/training/phase22-stable-toposort-diverse2500-chat-20260718-03/phase22-exit-evidence.json`,
handoff 0166, and ADRs 0141–0146.

The final release audit passes 1,187 source tests with two declared skips, Ruff,
283 generated-schema checks, and strict typing over all 14 Phase 22 production
and exit targets. Signed seven-component release
`fam-os-current-test-20260718-13` was atomically installed into the normal owner
prefix, diagnosed healthy, and started against the preserved durable state. Its
installed browser policy exactly matches source, and installed task
`task-6284a5f4-771c-47c5-989b-baadf91d5f38` repeated the owner-reported
`What's in this project?` VS Code flow through diagnostics, active editor,
selection, local inference, and a grounded terminal result. See handoff 0167.

---

## Phase 23 — Final release qualification

**Goal:** Prove the complete behavior from signed installed artifacts.

- [x] 23.1 Pass clean base, mathematics, verification, media, hardware, training, and VS Code profiles.
- [x] 23.2 Pass all suites from built release artifacts.
- [~] 23.3 Pass every installed local, application, memory, escalation, remote, and factory scenario.
- [x] 23.4 Pass independent CPU-only and full-workstation matrices.
- [ ] 23.5 Pass a minimum 24-hour installed pressure, failure, restart, and rollback soak.
- [x] 23.6 Prove Console state is live and authoritative.
- [ ] 23.7 Complete independent human security review with no blocking findings.
- [ ] 23.8 Prove signed fresh-user install, update, rollback, recovery, and total removal.

Interactive Phase 23 readiness testing found and corrected an installed
application-failure livelock: rejected observation evidence now produces a
durable terminal failure, previously stranded terminal plans are reconciled on
snapshot, the Console uses one bounded task-watch path without repainting an
unchanged revision, the loopback Console port supports an immediate clean
restart, and signed updates preserve existing read-only trust keys. Signed test
release `fam-os-current-test-20260717-12` first installed this repair. The current
Console additionally distinguishes an expired session from transient transport
loss, defaults application questions to observation-only capabilities, permits
an unspecified active-editor target only when the connector resolves it inside
its registered workspace, and rejects out-of-scope returned evidence. Release
assembly now compiles the connector before signing, and same-version connector
updates atomically replace stale code. A physical installed request completed
diagnostics, active-editor, selection, inference, and release steps with grounded
assurance instead of remaining on `Fail safely`. A second owner-reported run
then exposed a narrower durable mismatch: its plan was terminal while its
inference execution remained unfinished for about 92 minutes. Core now waits
for terminal evidence ownership and reconciles that state fail-closed if the
worker stops, while the browser combines SSE with a two-second authoritative
status watchdog. The owner then found one remaining browser race: an
already-queued live event could replace a terminal HTTP snapshot at the same
Shell revision after the watchers had closed. Browser task updates now reject
other-task, older-revision, and terminal-to-nonterminal transitions. A dedicated
JavaScript regression replays that exact terminal-then-stale ordering. Signed
release `fam-os-current-test-20260717-12` physically proved an unavailable
observation reached a terminal result in 0.56 seconds and a live VS Code
observation request completed with grounded assurance in 5.23 seconds; all
durable inference, plan, and application records were terminal. Handoffs 0157,
0162, 0163, and 0164 record the exact evidence. Signed release
`fam-os-current-test-20260718-13` now carries the repair together with the
completed Phase 22 source. It diagnoses healthy, is running on port 8765, and
repeated the owner-reported VS Code project question to a grounded terminal
result in about 22 seconds. Handoff 0167 records the installed proof.

Phase 23 Console readiness now includes a conversation-first Weave surface in
signed release `fam-os-current-test-20260718-14`. The scrollable user/FAM
transcript is the primary surface, the composer remains directly below it, task
scope is available without dominating the prompt, and the live plan remains a
separate activity inspector. Released answers use a bounded adaptive typewriter
reveal, expose the complete answer immediately to assistive technology, skip
motion when requested, and return the transcript to the beginning of the newest
FAM answer when reveal completes. Browser-local turns remain available during
the current page session; durable cross-restart conversation history is not
claimed. Handoff 0168 records the signed installation and exact UI regressions.

Interactive two-turn testing then exposed a session-input ordering defect: Core
placed the active question before the previous conversation, allowing the small
language model to repeat the final old assistant answer. Supporting memory and
authorized application observations now precede an explicitly labelled current
request; context-free prompts remain unchanged. The system contract also forbids
repeating an earlier answer unless asked and requires an explicit unavailable
answer when no authorized application/workspace context exists. Signed release
`fam-os-current-test-20260718-16` completed `Hey who are you?` followed by `What
is your current workspace?` as two distinct installed Console requests. The
second candidate answered only that no workspace context was selected and did
not repeat the identity response. Handoff 0169 records the regression, complete
source validation, signed update, and installed evidence.

Owner testing of a create-folder request then exposed a more fundamental policy
defect: imperative machine work could enter ordinary conversation inference and
the model could describe an action as completed without an authorized provider
invocation. Signed release `fam-os-current-test-20260718-20` moves action intent
ahead of model selection, returns model-free `action_proposal` or
`capability_unavailable` outcomes when authority is incomplete, and reserves
`action_receipt` for independently verified capability execution. Installed
evidence proves four unsupported action paraphrases were withheld without an
action attempt; a pending named-folder request consumed its follow-up path and
was denied without mutation; and an approved owner-scoped directory create plus
identity-bound empty-directory reversal both returned verified receipts. Core
also rejects a verified model claim when its plan lacks bound action-result and
audit evidence, and replaces candidate prose with a deterministic receipt when
that evidence exists. The release diagnoses healthy and serves the Console on
loopback port 8765. See
`artifacts/product/phase23/action-intent-firewall.json`, handoff 0170, and ADR
0147.

The same audit corrected two additional production reachability defects. The
Console now represents each registered VS Code workspace as a distinct scoped
context, binds the chosen workspace URI to the task, excludes unavailable
instances, and has a token-safe `fam-os console` launcher. A restarted live
service completed bootstrap exchange and authenticated snapshot retrieval with
HTTP 200. Handoff 0171 records the source and operational proof.

Installed resource selection and predictive prewarming now share live host,
VRAM, validation-profile reserve, managed-cgroup, battery, thermal, load, and
idle policy. Focused and composition blast-radius suites passed, and all 285
serialized schemas remain valid. This removes the prior path that could select
or prewarm a stronger tier while protective policy was active. See handoff 0172
and ADR 0148.

Production model operations now use one serialized residency facade. The task
worker holds request-scoped durable leases; document embedding uses encoder
context admission; managed Ollama uses stable warm-only confirmed eviction;
external Ollama cannot be evicted; startup state follows one provider snapshot;
and dead process leases recover before reconciliation. Architecture coverage
proves live adaptation, document memory, remote execution, factory inference,
and the Core gateway cannot be composed around the raw runtime. Twenty-eight
focused residency/repository tests, 50 product blast-radius tests, and the full
1,241-test source suite passed with two declared environment/hardware skips.
This is source evidence only; a fresh signed installed matrix remains required.
See handoff 0173 and ADR 0149.

The retrieval portion of the same audit found a false-verification path: an
exact citation could satisfy provenance checks while answering a different
question. Retrieval declarations are now query-bound, current candidates are
strictly extractive, both selected sources and cited answer spans must cover the
deterministic query obligation, and frozen query-unbound declarations remain
readable but cannot authorize a new pass. A complete dependency wheelhouse was
also required after the signed updater correctly rejected an incomplete bundle.
Release `fam-os-query-bound-20260718-02` passed offline installation and atomic
activation, then live Shell verified the exact FAM_OS identity with two package
citations and rejected the previous residency-smoke prompt without inference.
The service runs from the installed active tree with restart-on-failure and the
Console returns HTTP 200. See handoff 0174 and ADR 0150.

The clean-artifact audit then found that source execution and signed bundles
were hiding two wheel defects: production verifier declarations/bindings and
the runtime model catalog were not package data. A wheel-only service therefore
lost declared verifiers and its embedding tier, disabling document indexing.
Both canonical configuration families now ship as exact-copy package resources
behind signed-release and source-tree precedence, with drift regressions. The
new split Phase 23 matrix runner builds one wheel, removes checkout import
overrides, installs every profile in a fresh environment, records exact package
versions/import origins/skips, discovers the live `*_smoke.py` hardware suite,
and separately compiles, tests, packages, installs, lists, removes, and hashes
the VS Code VSIX. Consolidated run `phase23-required-20260718-01` passed Base,
Verification, Mathematics, Media, Hardware, Training, and VS Code against wheel
SHA-256 `a7a8410f37d9e8a604d69094b054a98acfb31374b699a7e92717feb1e6229f2c`.
Each profile ran all 1,257 standard tests; Hardware additionally discovered 11
explicitly opt-in live smokes, and Media reduced the standard environment skips
from three to two by exercising Pillow. This completes 23.1 and 23.2 only. See
`artifacts/product/phase23/profile-matrix/phase23-required-20260718-01/profile-matrix.json`,
handoff 0176, and ADR 0151.

At that point 23.3, 23.6, and 23.8 remained incomplete: explicit granted
whole-workspace indexing, clean-release matrices, soak, rollback, and removal
evidence had not yet been gathered.

The installed-scenario audit then traced restart action recovery and found the
Phase 17 reconciler was never called by `LocalProductService`. Source now runs a
cross-repository coordinator before client startup, requires fresh approval
when restart follows confirmation, re-observes owner-directory postconditions
without provider invocation, commits crash-idempotent audit/result evidence,
and leaves unsupported uncertain actions in an explicit worker-blocking recovery
state. Real service restart tests cover awaiting approval, approved authority
discard, denial, post-mutation recovery, and inconclusive connector state. This
is a prerequisite repair, not Phase 23.3 installed-candidate evidence. See
handoff 0177 and ADR 0152.

Fresh signed installed matrix `phase23-installed-20260718-11` now passes all
seven local scenario groups from one candidate wheel: verified local work,
approval-restart and uncertain-action recovery, outbound/inbound MCP,
whole-workspace memory and restart grounding, bounded Laguna/Gemma escalation,
media, same-host remote execution, and the complete Factory conversion,
package, canary, activation, rollback, reactivation, retirement, and removal
lifecycle. The Factory driver and action fault injector expose only the
candidate-installed Python tree; Factory evidence records that no Phase 22
acceptance composition was imported. Candidate removal and preservation of the
owner service both pass. The remote result remains explicitly same-host, so
23.3 stays partial until Phase 21.7 supplies two physical machines.

Installed hardware matrix `phase23-hardware-20260718-06` independently passes
the `compat-cpu-16gb` and `full-reference-workstation` profiles. The constrained
profile proves the 16 GiB maximum, 14 GiB high watermark, CPU-only provider,
zero swap/OOM/VRAM, and retained host reserve. The full profile proves all 24
logical CPUs, 64 GiB-class RAM, RTX 5080 VRAM use, storage capacity, no
artificial memory ceiling, and retained reserve. Both profiles complete
verified work and query-bound grounded memory before and after restart; the
full profile also passes isolated Laguna and Gemma probes. This completes 23.4.

The same two runs complete 23.6 without relying on directory counts. Console
CPU, schedulable RAM, VRAM, storage, policy, signed catalog, and residency are
cross-checked against independent host, cgroup, filesystem, NVIDIA, and Ollama
telemetry. Durable terminal results, active permissions, verified application
audit records, and document-index grants change with real operations and
persist across restart. A candidate-installed missing-key state reports
recovery mode, does not regenerate the owner key, and marks every unavailable
provider explicitly instead of displaying stale state.

The first 23.5 qualification attempt then failed after 21 seconds during the
healthy verifier restart check. The audit proved installed systemd services
were truly AppArmor `unconfined`, unlike the development terminal's named
profile, and Ubuntu's restricted unprivileged-userns policy prevented
Bubblewrap namespace setup. `NoNewPrivileges=true` also correctly blocked an
in-process profile transition. Source now signs `fam-os-userns`, detects when
the host requires it, launches only the short-lived verifier through a
manager-created transient service carrying that profile, keeps the main daemon
locked down, and injects the same sandbox into normal and Factory verification.
Missing profile application is `unavailable`, never a candidate failure.
`fam-os host-security diagnose` proves the installed sentinel boundary. The
24-hour clock must restart after an administrator loads the dedicated profile;
the failed short run does not advance 23.5. See ADR 0155 and handoff 0179.

The same audit found 23.8 had neither a complete user-removal implementation nor
an installed lifecycle runner. State and runtime roots now receive exact
UID/purpose/path markers. Confirmed removal validates every authority before
mutation, stops both managed services, removes only the owned unit link and VS
Code connector, deletes marked runtime and durable state/model roots, and
deletes the signed prefix last. The first lifecycle preflight then exposed a
second real defect: missing launchers disappeared from a live filesystem glob,
so diagnosis could falsely report a damaged installation as healthy. The
versioned installation marker now records every expected generated launcher,
unit, and trust key by safe path and SHA-256 digest; diagnosis, repair, update,
rollback, and receipts consume that ledger. Qualification tools also use one
canonical `tools.*` package identity so discovery does not depend on invocation
path or `PYTHONPATH`.

The fourth lifecycle preflight passes clean install, signed update, rollback,
damaged-launcher diagnosis, repair, connector install, installed-service HTTP
200, and complete removal. It continues after the required sandbox probe so the
independent evidence is retained; the overall result correctly remains failed
because the dedicated AppArmor profile is not loaded. Phase 23.8 therefore
remains open until that profile is loaded and the exact final post-soak signed
candidate completes every event. See ADRs 0156-0157 and handoffs 0179-0180.

**Exit gate:** Every subsystem is operationally proven by installed-release
evidence, and no final evidence depends on acceptance-only composition.

**Final acceptance:** FAM_OS visibly behaves as a resource-aware intelligence
layer woven through the workstation—not as a single-model chatbot—and every
significant claim is reproducible from the shipped release.

## Companion engineering plan status

`MASTER_PLANv2.md` is the additive authority for Phases 24–31. As of
2026-07-19, the ordinary single-repository natural edit, verify, checkpoint,
apply, reverify, and local-commit lifecycle has signed installed evidence.
History-preserving rollback, separately approved publication, durable
natural-failure incident attachment, and automatic feature branching are
source-composed in Handoffs 0239–0242,
and are present in isolated signed candidate `phase30-integrated-20260719-1`.
Its 62 installed-package tests pass, but its live host-security qualification
fails closed because `fam-os-userns` is not loaded; it is not evidence from the
active installed release. Phase 30 therefore
remains open for live installed qualification, complete auxiliary capability
and governance orchestration, full Console/Shell controls, and one complete
installed composition. Phase 31 still requires the final signed profile and
dependency matrices, a minimum 24-hour mixed engineering pressure soak, and an
independent signed human security review. ADR 0174 prevents those missing
proofs from being relabeled complete.

The latest source milestones compose two exact apply gates: ADRs 0209 and 0216
plus Handoffs 0244 and 0251 add owner-encrypted policy-selected signed
independent-review checkpoints, typed resolution, and truthful waiver, while ADR 0210
and Handoff 0245 add trusted generated-documentation admission, source/output
rehashing, traceability, and stale-output blocking. The review and regenerated
documentation paths are source-composed but still lack a new signed installed
and live proof, and therefore do not change Phase 30 completion status.

ADR 0211 and Handoff 0246 now add release-signed deterministic generators for
all five documentation artifact kinds and prove them from healthy isolated
release `phase30-governance-20260719-3` with 74 installed-package tests and no
checkout import. The host production verifier remains fail-closed because
`fam-os-userns` is not loaded; automatic stale regeneration, governance-file
digest binding, complete trace creation, and final installed scenarios remain
open. Phase 30 completion status is unchanged.

ADR 0218 and Handoff 0253 now source-compose Phase 27.11 local runtime
diagnostics into the same natural task, grant, budget, candidate checkpoint,
post-apply verification, Console, and Shell lifecycle. Exact performance
baselines are captured before edits, and the signed release owns the bounded
diagnostic helper instead of depending on the builder checkout. Distributed
service tracing and newly signed installed/both-profile qualification remain
open, so neither Phase 27.11 nor the overall companion plan changes to
complete.

ADR 0219 and Handoff 0254 now source-compose local SQLite engineering into the
same natural task lifecycle. Deterministic target and reversible-migration
planning, disposable forward/rollback rehearsal, encrypted candidate backup,
fresh-authority recovery, exact database changeset evidence, independent owner
post-apply schema/data observation, commit, restart reconstruction, and
history-preserving rollback are joined behind the ordinary checkpoint. Private
candidate recovery evidence remains outside the user changeset. PostgreSQL and
MySQL, a new signed installed release, independently enforced profiles, soak,
and human review remain open; Phase 27.12 and the overall companion plan stay
incomplete.

ADR 0220 and Handoff 0255 correct natural request routing without widening
authority: explicit Application Fabric context takes precedence over the
repository lifecycle, ambiguous `use` requests require a concrete machine
target before entering the action firewall, and delegated MCP admission may
return an immediate terminal result. Focused legacy and protocol regressions
pass. The latest complete source discovery runs 1,828 tests with 15 expected
fail-closed host-security failures and one intermittent legacy Shell
`core_unavailable` error that passes twenty consecutive isolated repetitions.
That internal qualification item and all previously open installed gates remain
open.

ADR 0221 and Handoff 0256 now source-compose one exact natural static-preview
integration environment into the master lifecycle. A release-signed
loopback-only recipe runs only after candidate verification; exact READY,
service-health, and terminal cleanup receipts become changeset evidence. After
approval, a separate environment runs against a fresh clone of the owner
workspace and must clean successfully before local commit. Console and Shell
surface both receipt sets, and restart reconstructs the terminal records.
Focused, schema/UI, architecture, and real installed-process/restart suites
pass, and the latest complete source discovery executes 1,836 tests with the
same 15 fail-closed host-verifier failures, no internal errors, and two skips.
Natural multi-service/browser/container/cluster composition, network and secret
ceremonies, remote databases, a new signed installed candidate, both enforced
profiles, soak, and human review remain open; Phase 27.13 and the companion
plan therefore remain incomplete.

ADR 0222 and Handoff 0257 extend that source slice to an exact two-service
natural environment. Explicit API/backend/full-stack wording plus a regular
root `api.py` selects a release-signed fixed Python entrypoint, while the
static service uses its separate signed template and depends on API health.
Distinct loopback ports, fixed health contracts, candidate and fresh-owner
cleanup evidence, and the existing commit/restart path remain mandatory. A
real Bubblewrap/systemd scenario makes both services healthy and removes both
scopes. The 124-test affected matrix, 41 architecture tests, 414 schemas, UI
syntax, and diff checks pass. Complete source discovery now executes 1,840
tests with the unchanged 15 fail-closed host-verifier failures, no errors, and
two skips. General declarative services, browsers, containers, clusters,
network/secret ceremonies, remote databases, signed installed qualification,
profiles, soak, and human review remain open.

ADR 0223 and Handoff 0258 add the public exact-version
`fam.integration.json` service-graph contract. Natural generation sees only
the closed `python_api`/`static_site` role vocabulary, logical IDs, and acyclic
dependencies; it never sees recipe coordinates. Core rejects duplicate keys,
unknown fields, wrong versions, intent expansion, missing fixed entrypoints,
and role omission, then maps admitted roles to release-signed templates. The
declaration is part of the owner changeset/commit and is decoded again from the
fresh post-apply clone. The affected 134-test and 41-test architecture suites
pass, all 415 schemas validate, and complete source discovery runs 1,845 tests
with the same 15 fail-closed host-verifier failures, no errors, and two skips.
Additional browser/container/cluster templates, network/secret ceremonies,
port leasing, remote databases, signed installed qualification, profiles,
soak, and human review remain open.

Handoff 0259 advances that companion-plan slice to
`installed_component_tested`. Fresh signed release
`phase30-natural-integration-20260719-1` installs healthily and passes 100
installed-package-first tests with checkout-import rejection, both exact
release-owned API/static recipes, all 415 schemas, and real two-service health
and cleanup. The durable artifact deliberately remains top-level failed because
the independent production verifier cannot apply the absent root-owned
`fam-os-userns` AppArmor profile. The live service was not changed. General
browser/container/cluster composition, race-free port leasing, explicit
natural network/opaque-secret ceremonies, remote databases, both profiles,
soak, and human review remain open; Phase 27.13 and the companion plan remain
incomplete.

ADR 0224 and Handoff 0260 source-compose the previously missing separate
natural integration-resource ceremony. Explicit canonical network destinations
and opaque secret references become a second exact task-scoped grant, never
ordinary task authority or service-declaration content. Console and Shell show
its complete scope, byte ceiling, and digest at a distinct owner checkpoint;
encrypted proposal record v2 preserves it with v1 compatibility. Candidate and
post-apply planners re-derive scope from the original intent and reject
expansion before existing integration authorization and enforcement services
run. The 136-test affected matrix and 41 architecture tests pass; complete
source discovery runs 1,853 tests with only the unchanged 15 host-security
failures, no errors, and two skips. Signed-installed/live broker and secret
lifecycle proof, remote databases, additional templates, port leasing,
profiles, soak, and human review remain open, so Phase 27.13 and the companion
plan remain incomplete.

ADR 0225 and Handoff 0261 source-compose a third fixed natural service role for
isolated PostgreSQL. Owner intent and the ADR 0224 resource checkpoint bind one
opaque password ref and a visible 256 MiB ephemeral-storage ceiling; the model
cannot select image, digest, command, health, port, secret value, or budget.
Stable template consumers make the same separately provisioned ref usable in
candidate and fresh-owner post-apply runs. A real Core/Docker test proves the
digest-pinned PostgreSQL 17 image, file-only `POSTGRES_PASSWORD_FILE`, signed
`pg_isready`, and cleanup with no leftover container/network. The internal
network exposes no host port, so remote target and migration support remain
explicitly open. The 121-test affected matrix and 41 architecture tests pass,
and all 415 schemas validate. This does not complete Phase 27.12, 27.13, or the
companion plan.

Handoff 0262 advances that isolated PostgreSQL service to
`installed_component_tested`. Signed complete release
`phase30-natural-postgresql-20260719-2` loads FAM_OS only from its immutable
installed root and passes 107 package-first tests, including real
digest-pinned PostgreSQL file-secret injection, signed health, and cleanup with
no host port or leftover Docker resources. Installation is healthy; the
separately recorded production-verifier result remains unavailable because
`fam-os-userns` is absent. The durable artifact is
`artifacts/product/phase30/natural-postgresql-install-20260719-01/evidence.json`.
This is not live activation or remote migration proof, so Phase 27.12, 27.13,
and the companion plan remain incomplete.

ADR 0226 and Handoff 0263 add the isolated PostgreSQL migration lifecycle:
fixed non-superuser `fam_migrator`, bounded forward/reverse pairs, encrypted
backup, transaction probe, exact schema/data states, repeat forward, fresh
restore, and fresh-owner post-apply proof. Signed release
`phase30-postgresql-migrations-20260719-3` exposes 417 schemas and passes 119
installed-package-first tests. It has no host port, external/production target,
or MySQL authority, so Phase 27.12/27.13 and the companion plan remain open.

ADR 0227 and Handoff 0264 correct source admission for ordinary generated
dependency/cache links. `.next`, `node_modules`, build, cache, virtual-
environment, and coverage trees are pruned without following or copying them;
authoritative source symlinks/hardlinks remain rejected. The selected real
npm/Next.js repository now produces 138 observations and a 238-entry link-free
candidate, with 23 focused security/workspace tests passing. This is developer
source evidence on port 8877, not signed live completion of Phase 30.1.

ADRs 0228-0229 and Handoff 0265 advance the companion plan with direct signed
installed CLI evidence. Release `fam-os-natural-engineering-20260719-10`
accepted two plain-language tasks through `fam-shell`: it edited a real-project
clone and created a new ES-module implementation plus Node tests, then ran
candidate verification, exact approvals, transactional apply, fresh
reverification, task-derived feature-branch commits, and optional rollback
decisions. The independent terminal test rerun passed, as did 58 affected, 11
adversarial/transactional, and 41 architecture tests. Phase 30.1 remains open
for a deliberately exercised
live repair/escalation path, separately approved publication, and the complete
exit scenario matrix.

ADR 0230 and Handoff 0266 add an owner-selected ChatGPT-authenticated Codex
engineering provider without moving authority out of FAM Core. Signed release
`fam-os-natural-engineering-20260719-12` used `gpt-5.6-sol` for bounded,
effect-free candidate generation while FAM retained repository inspection,
plan validation, candidate isolation, sandbox execution, two exact approvals,
transactional apply, reverification, rollback, and Git delivery. A real
installed natural-language task changed two Python files, passed four candidate
and four post-apply tests, created clean commit
`43aea1e2afa9546bec4e2c2b4e10af43d12b184e`, and passed an independent test
rerun. The acceptance also found and fixed a lifecycle defect where
verifier-generated `__pycache__` blocked changeset preview. Seventy-six focused
and polyglot tests and all 41 architecture tests pass. Phase 30.1 remains open
for the previously listed repair/escalation, publication, and full scenario
matrix gaps; this provider slice does not close the phase by itself.

ADRs 0231-0232 and Handoff 0267 correct conversational plan continuation and
repository toolchain routing. Plan references now resolve only for the same
owner, authenticated session, and canonical workspace, while the current
message alone determines authority. Recognized manifests now dominate
toolchain selection, so an unrelated utility file cannot impose an absent test
suite. Signed release `fam-os-natural-engineering-20260719-13` completed a real
authenticated Console HTTP plan-to-implementation sequence with
`gpt-5.6-sol`: plan-only analysis, `Ok, implement the plan`, Node-only
verification despite an unrelated Python file, exact changeset approval,
apply, post-apply verification, and clean commit
`ed860c64bff46734f56f7981eb445150fe3810e2`. Three independent Node tests
passed. Phase 30.1/30.5/30.9 remain open for restart-persistent plan references,
zero-test acceptance policy, installed repair/escalation, publication, and the
complete exit scenario matrix.
