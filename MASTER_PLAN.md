# FAM_OS Master Plan

## Purpose

This document is the authoritative implementation sequence for FAM_OS. Work must advance a named step, satisfy its exit gate, and create a handoff for every major change.

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

**Current Phase 2 evidence:** Core request/routing/plan/result contract families for step 2.1 are recorded in `handoffs/0013-core-execution-plan-contracts.md`, `docs/protocols/CORE_CONTRACTS.md`, and ADR 0014. Versioned host-inventory and effective-resource-budget contract families for step 2.2 are recorded in `handoffs/0014-hardware-resource-contracts.md`, `docs/protocols/HARDWARE_RESOURCE_CONTRACTS.md`, and ADR 0015. Expert, verifier, connector, and memory-record manifests for step 2.3 are recorded in `handoffs/0015-component-manifest-contracts.md`, `docs/protocols/MANIFEST_CONTRACTS.md`, and ADR 0016. Python Application Fabric contracts, the VS Code-shaped fake connector, and transport/registry ports for steps 2.4, 2.5, and 2.9 are recorded in `handoffs/0012-application-fabric-contracts.md`, `docs/protocols/APPLICATION_CONTRACTS.md`, and ADR 0013. Structured failures, application failure evidence, explicit degradation, and safe final-result mapping for step 2.6 are recorded in `handoffs/0016-structured-failures-degradation.md`, `docs/protocols/FAILURE_DEGRADATION_CONTRACTS.md`, and ADR 0017. The first 27 strict serialized roots, exact alpha compatibility, fixed fixtures, cross-contract validation, and the public-schema ADR audit for steps 2.7 and 2.10 are recorded in `handoffs/0017-strict-schema-compatibility.md`, `docs/protocols/SERIALIZED_SCHEMA_COMPATIBILITY.md`, and ADR 0018. Deterministic defaults/profile/discovery/user/session composition, monotonic restriction policy, ordered audit decisions, and seven additional strict configuration roots for step 2.8 are recorded in `handoffs/0018-configuration-layering.md`, `docs/protocols/CONFIGURATION_LAYERING.md`, and ADR 0019. Concrete strict-schema minimum/full profile documents, a separate service envelope, and separation of reusable policy from captured machine state for step 2.11 are recorded in `handoffs/0019-dual-validation-profiles.md`, `docs/protocols/VALIDATION_PROFILE_DOCUMENTS.md`, and ADR 0020. Unified profile/budget admission, one Ollama/systemd service path, shared workload entrypoints, and profile-derived placement/report constraints for step 2.12 are recorded in `handoffs/0020-profile-driven-benchmark-composition.md`, `docs/operations/PROFILED_BENCHMARKS.md`, and ADR 0021. Privacy-reviewed live discovery, strict full-budget composition, expanded CPU/I/O/VRAM/model telemetry, and the canonical raw full-workstation baseline for step 2.13 are recorded in `handoffs/0021-full-workstation-smoke-baseline.md`, `docs/operations/FULL_WORKSTATION_SMOKE.md`, and ADR 0022. The original baseline remains an immutable failed-quality result with safe withholding. Strict conformance, explicit test disclosure to repair only, decomposed examples, and successful independent Laguna/Gemma full-workstation evidence for step 2.14 are recorded in `handoffs/0026-strong-model-quality-rerun.md`, the same operations guide, and ADR 0027. A concrete authenticated local transport is not yet implemented.

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

**Current Phase 3 evidence:** The canonical typed capability/non-goal boundary, current versus planned authority, user-session trust scope, and authenticated-caller assumptions for step 3.1 are recorded in `handoffs/0022-supervisor-boundary.md`, `docs/architecture/SUPERVISOR_BOUNDARY.md`, and ADR 0023. Authorization-injected principal/session ownership, independent `fam-` namespace restriction, exact-definition claims, idempotent lifecycle semantics, and a cleaned-up live user-service smoke for step 3.2 are recorded in `handoffs/0023-owned-service-lifecycle.md`, `docs/architecture/OWNED_SERVICE_LIFECYCLE.md`, and ADR 0024. Exact CPU/RAM/swap/task requested-versus-applied cgroup checks, explicit unbounded-versus-unavailable semantics, compensating stop, and a cleaned-up live constrained-service smoke for step 3.3 are recorded in `handoffs/0024-applied-resource-limits.md`, `docs/architecture/APPLIED_RESOURCE_LIMITS.md`, and ADR 0025. Opaque principal/session/service-scoped access grants, single-use revocation, provider-neutral allowlists, adapter-owned paths, and a live allowlist-only filesystem/device namespace proof for step 3.4 are recorded in `handoffs/0025-capability-access-grants.md`, `docs/architecture/CAPABILITY_ACCESS_GRANTS.md`, and ADR 0026. Required privacy-bounded request/outcome records, exact operation linkage, canonical JSONL encoding, private locked append, SHA-256 chain verification, duplicate-event rejection, compensation, and a live audited-service proof for step 3.5 are recorded in `handoffs/0027-immutable-supervisor-audit.md`, `docs/architecture/IMMUTABLE_SUPERVISOR_AUDIT.md`, and ADR 0028. Failed-to-inactive recovery, safe owned-service termination, deterministic grant retirement, systemd failed-state retention/reset, and a live exit-code failure cleanup proof for step 3.6 are recorded in `handoffs/0028-safe-service-recovery.md`, `docs/architecture/SAFE_SERVICE_RECOVERY.md`, and ADR 0029. The explicit attacker model, option/control/size/path hardening, bounded control-group termination, intelligence-import guard, adversarial tests, and combined live Phase 3 exit proof for step 3.7 are recorded in `handoffs/0029-supervisor-threat-model.md`, `docs/security/SUPERVISOR_THREAT_MODEL.md`, and ADR 0030. The external authentication transport, durable registries, dedicated installed AppArmor profile, trusted external audit-head checkpoint, and approved-command digest binding remain future work.

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

**Exit gate:** The full lifecycle passes against fake experts, applications, and verifiers with no inference runtime or desktop automation.

**Current Phase 4 evidence:** Steps 4.1-4.6 are recorded in handoffs 0030-0035 and ADRs 0031-0036 with their linked protocol documents. Replay-safe cancellation, trusted-deadline timeout, typed degradation, and absorbing terminal controls for step 4.7 are recorded in `handoffs/0036-core-control-transitions.md`, `docs/protocols/CORE_CONTROL_TRANSITIONS.md`, and ADR 0037. Registry-backed terminal release, candidate-linked passing acceptance, blocking degradation, and content-free non-release policy for step 4.8 are recorded in `handoffs/0037-core-final-result-policy.md`, `docs/protocols/CORE_FINAL_RESULT_POLICY.md`, and ADR 0038. The admission-to-terminal fake-driven matrix for verified release, denial, expiry, cancellation, timeout, degradation, attempt exhaustion, replay, and failed-content withholding for step 4.9 is recorded in `handoffs/0038-core-lifecycle-matrix.md` and `tests/integration/test_core_lifecycle_end_to_end.py`.

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

**Current Phase 5 evidence:** Steps 5.1-5.5 are recorded in handoffs 0039-0043 and ADRs 0039-0043 with their linked protocol documents. Bounded shell-free process execution, scoped hash/precondition-bound atomic files, MIME provenance, exact primitive D-Bus calls, prepared portal URIs, allowlisted tool mappings, OS-tool registration, and live-safe reference probes for step 5.6 are recorded in `handoffs/0044-deterministic-linux-capabilities.md`, `docs/protocols/DETERMINISTIC_LINUX_CAPABILITIES.md`, and ADR 0044. Provider-isolated AT-SPI discovery, bounded opt-in-text observations, password-content redaction, fingerprinted stale-object rejection, allowlisted two-stage actions, explicit unavailability, and a mutation-free live desktop probe for step 5.7 are recorded in `handoffs/0045-linux-accessibility-bridge.md`, `docs/protocols/LINUX_ACCESSIBILITY_BRIDGE.md`, and ADR 0045. The unprivileged color-free `fam-shell` terminal, versioned Ask/context/plan/progress/approval/cancellation/result contracts, Core-side lifecycle projection, monotonic presentation reducer, terminal-control neutralization, and peer-authenticated bounded Unix transport for step 5.8 are recorded in `handoffs/0046-fam-shell-mvp.md`, `docs/protocols/FAM_SHELL_MVP.md`, and ADR 0046. The off-by-default VS Code extension, provider-neutral TypeScript connector SDK, bounded semantic observations, exact revision-bound reversible workspace edits, correlated native transport handshake, connector-owned schemas, and cross-language interoperability proof for step 5.9 are recorded in `handoffs/0047-native-vscode-semantic-connector.md`, `docs/protocols/VSCODE_SEMANTIC_CONNECTOR.md`, and ADR 0047. The exact active-window screen contract, independent capture/input availability, bounded PNG provider, allowlisted XTest primitives, exact-scene revalidation, explicit Wayland degradation, and non-mutating live X11 metadata proof for step 5.10 are recorded in `handoffs/0048-restricted-screen-input-fallback.md`, `docs/protocols/RESTRICTED_SCREEN_INPUT_FALLBACK.md`, and ADR 0048. Exact request/plan/capability/grant/proposal/approval binding, trusted pre/postcondition verification, atomic execution replay prevention, content-free required action audit, safe output withholding, and explicit recovery metadata for step 5.11 are recorded in `handoffs/0049-required-application-action-safety.md`, `docs/protocols/APPLICATION_ACTION_SAFETY.md`, and ADR 0049. The authenticated Shell vertical run through bounded AT-SPI, official-SDK MCP, deterministic file/test adapters, a local Ollama expert, the real isolated VS Code extension, approved verified edit, durable audit, integration-level reliability/resource measurements, and MCP-unavailable success for step 5.12 is recorded in `handoffs/0050-cross-application-acceptance.md`, `docs/operations/CROSS_APPLICATION_ACCEPTANCE.md`, ADR 0050, and `artifacts/application_fabric/phase5_acceptance.json`.

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

- [x] 14.1 Complete threat models and external security review.
- [x] 14.2 Add atomic updates and rollback for services, schemas, experts, and connectors.
- [x] 14.3 Add multi-user isolation and recovery mode.
- [x] 14.4 Add long-running thermal, storage, memory, and crash tests.
- [x] 14.5 Make FAM_OS trivial to install, update, diagnose, repair, and completely remove on Linux.
- [x] 14.6 Complete the production FAM Shell and Console for resources, experts, permissions, memory, audit history, and recovery.
- [x] 14.7 Publish reproducible minimum-hardware and full-reference-workstation benchmarks.

**Exit gate:** FAM_OS can be installed and removed safely, survives extended operation, and provides complete user visibility and control.

**Exit status:** Complete. The aggregate product gate reran safe installation,
damage diagnosis, repair, removal, signed atomic update and rollback, owner
isolation, recovery denials, and complete Console visibility. It binds the live
five-minute thermal/storage/memory/crash qualification and the profile-separated
reference benchmarks. Evidence is in `artifacts/product/phase14-exit.json` and
`handoffs/0122-phase14-product-exit.md`.

---

## Immediate next step

Run the final repository-wide audit and begin release-candidate packaging. A
third-party human penetration test remains explicitly uncompleted and must not
be represented as certification.

**Final audit status:** Reopened. The component and package gates passed, but the
installed user service referenced a missing module and no installed-daemon test
proved a real Shell request through Core and Ollama. Phase 15 is required before
the project may again claim Master Plan completion.

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
