# FAM_OS Final Integration and Gap-Closure Plan

## Status

FAM_OS is **integration incomplete**. Phases 16–20, steps 21.1–21.6, and Phase
22 are complete with signed installed evidence. Phase 21.7 physical
qualification is in progress because a second physical Linux machine is still
required. Final release qualification remains open.
This document is the controlling detail for Phases 16–23; `MASTER_PLAN.md`
remains the authoritative sequence.

The machine-readable source of current maturity is
`configs/integration/coverage.json`. A subsystem is not complete because it has
a schema, a passing harness, or a generated evidence file. Final completion
requires that it be reachable from the installed product and supported by
installed operational evidence.

## Product finish line

The current installed foundation is:

```text
Console / Shell / VS Code / MCP
              |
       durable FAM Core
              |
 Plan -> signed expert selection -> inference
              |
 Approval -> action -> declared verifier -> durable evidence
              |
 bounded session memory + opt-in encrypted document indexes
```

The completed installed path is:

```text
Console / Shell / VS Code / MCP
              |
       durable FAM Core
              |
 Intent -> Context -> Plan -> Expert selection
              |                 |
 Application Fabric       Hardware Scheduler
              |                 |
 Approval -> Action -> Verification -> Evidence
              |
 Memory / Adaptation / Trusted devices / Expert Factory
```

This is not a claim that one physically oversized model can be made to fit into
limited memory. FAM_OS provides larger effective capability through specialist
routing, model paging, CPU/GPU/RAM/SSD placement, approved retrieval, bounded
escalation, and deterministic verification.

## Whole-project gap baseline

| Subsystem | Current reality | Required completion |
|---|---|---|
| Governance | Historical plan completion includes disconnected components | Preserve history and classify maturity truthfully |
| Installed service | Signed unified service reaches Core, experts, verification, applications, UI, memory, adaptation, trusted-device controls, and the Expert Factory | Pass the complete Phase 23 release-candidate qualification |
| Core | Durable transactional orchestration, restart recovery, and live providers | Final cross-profile and soak qualification |
| Expert Fabric | Live signed catalog, routing, activation, bounded Laguna/Gemma escalation, and signed specialist lifecycle | Consolidated Phase 23 clean-profile matrices |
| Scheduler | Live host/Ollama state, reserves, thermal/foreground policy, durable leases, managed confirmed eviction, and both signed hardware profiles drive selection and prewarm | Complete the 24-hour integrated pressure soak |
| Verification | Five declared domains and application postconditions run through installed Core and both signed hardware profiles | No verifier-specific implementation gap; retain coverage through the remaining product gates |
| Applications | Capability-driven native, deterministic, MCP, explicit fallback, and signed installed owner-workspace list/read/action paths | Add a bounded Core-owned multi-step repository tool loop; retain remaining Phase 23 gates |
| VS Code | Signed VSIX supports observe, preview, edit, save, verify, and undo | Phase 23 clean-profile matrices |
| MCP | Allowlisted clients and permission-filtered ingress reach Core | Fresh installed MCP matrix in Phase 23 |
| UI | Natural Shell and authenticated Console expose tasks, plans, evidence, approval, cancel, undo, owner workspace selection, Tool receipts, memory, adaptation, trusted-device controls, and Factory mutation routes | Complete the multi-step project workflow and retain remaining Phase 23 checks |
| Memory | Bounded exact-session memory, opt-in encrypted indexes, citations, management, and verified-outcome features are operationally proven | Phase 23 independent clean-profile matrices |
| Adaptation | Verified outcomes drive live advice and prewarm; owner controls, repeated drift evaluation, known-good rollback, restart, and reset are operationally proven | Phase 23 independent hardware/profile matrices |
| Multi-device | Persistent identity, pairing, TLS 1.3, signed capabilities, measured performance, privacy, minimum context, complete evidence, partial-output discard, and disconnect recovery pass through installed Core | Repeat the success/loss flow between two distinct physical Linux hosts |
| Expert Factory | Governed failure discovery, approved QLoRA, sealed held-out evaluation, signed package, canary, activation, rollback, retirement, and removal passed from an installed release | Phase 23 clean training profile and consolidated release-candidate scenario |
| Supervisor | Managed Ollama/workers, profile cgroups, restart reconciliation, and durable audit are production-wired | Integrated 24-hour pressure/crash/restart qualification |
| Product updates | Signed seven-component bundles, migrations, health checks, atomic activation, rollback, repair, and removal are implemented | Final trust-key ceremony and fresh-user install/update/rollback/recovery/removal matrix |
| Security | Automated component checks | Integrated threat testing and independent human review |
| Reliability | Five-minute component and 60-second installed tests | 24-hour installed failure and pressure qualification |
| Test environment | Default discovery needs undeclared optional dependencies | Clean, explicit dependency and hardware profiles |

## Maturity model

1. `contract_only`: a typed boundary or schema exists.
2. `component_tested`: the implementation passes isolated tests.
3. `acceptance_only`: a composed harness passes, but the installed product
   cannot reach the behavior.
4. `production_wired`: the installed composition can reach it.
5. `operationally_proven`: the shipped release has reproducible installed
   evidence, recovery behavior, and no open exit-gate gap.

Only `operationally_proven` satisfies the final target.

## Phase 16 — Rebaseline truth and integration ownership

- Amend `MASTER_PLAN.md` without rewriting historical phases; set overall
  status to integration incomplete.
- Maintain a strict, versioned integration coverage manifest for every
  subsystem and test it as a product contract.
- Append Phases 16–23 with unchecked exit gates.
- Use small composition modules for storage, Core, runtimes, applications,
  memory, Console, remote fabric, and factory. `LocalProductService` remains a
  lifecycle coordinator only.
- Split dependency intent into base, verification, mathematics, media,
  development, hardware, and training profiles, with clean-environment commands
  and expected hardware skips.
- Enforce an architecture rule that production composition cannot import
  acceptance harnesses or exit-evidence builders.

Exit gate: documentation and automated coverage checks report real maturity
without treating isolated evidence as installed behavior.

## Phase 17 — Durable production substrate and managed runtime

- Add an owner-private SQLite WAL database with ordered migrations for
  requests, plans, events, authorities, decisions, action state, evidence,
  experts, connectors, and adaptation metadata.
- Encrypt prompts, sensitive context, and memory with an owner-bound master key.
  Missing or corrupt keys over existing data enter recovery mode and never cause
  silent key replacement.
- Replace production in-memory registries with transactional repositories.
  Recovery may resume safe reads/inference, must request new approval for pending
  mutations, and must reconcile uncertain actions by postconditions before any
  retry.
- Make Supervisor own a dedicated Ollama user service, cgroup, model directory,
  health checks, and shutdown. Existing blobs may be linked only after digest
  validation.
- Apply profile-derived memory, CPU, process, and I/O limits while exposing the
  test workstation's 24 CPUs, about 64 GiB RAM, 16 GiB VRAM, and NVMe capacity
  with explicit OS headroom.
- Reconcile packages, runtime models, residency, connectors, and incomplete plans
  at startup.
- Ship a signed versioned bundle containing code, schemas, UI, units,
  connectors, and migrations. Support install, enable, update, rollback,
  diagnose, repair, and complete removal with safe XDG defaults.

Exit gate: killing and restarting FAM during inference, approval, and action
execution preserves state without replaying authority or losing evidence.

## Phase 18 — Unified Core, Expert Fabric, scheduler, and verification

- Replace `LocalInferenceShellGateway` with one production task gateway using
  admission, routing, plan lifecycle, attempts, approvals, actions,
  verification, and final-result policy.
- Classify conversation, grounded question, read-only task, mutating application
  task, code, math, retrieval, media, and administration. Model classification
  remains advisory; Core policy owns authority.
- Build the live catalog from enabled signed packages and discovered runtime
  bindings; remove the fixed-model production path.
- Begin with `qwen3:1.7b` for economical language/intent,
  `llama3.2:3b` for general synthesis, `qwen2.5-coder:7b` for economical code,
  `laguna-xs.2:q4_K_M` and `gemma4:26b` for bounded escalation,
  `nomic-embed-text` for retrieval, and `qwen3-vl:8b` plus declared media
  packages for vision/OCR/speech.
- Select with capability, verification history, context, latency, RAM, VRAM,
  CPU offload, SSD transfer, thermal state, and foreground pressure.
- Connect residency to real load/unload state and emit explanations plus measured
  placement results.
- Invoke declared verifiers. Code runs only in the sandbox; retrieval citations
  bind exact bytes; application actions require independent postconditions.
- Give repair attempts exact test sources, bounded failing inputs/outputs, and
  verifier diagnostics. Share one monotonic time/token budget and never weaken
  acceptance during escalation.
- Label output `unverified`, `grounded`, or `verified`; model text alone never
  proves an action.

Exit gate: a natural request traverses the real lifecycle, selects and escalates
experts as needed, verifies the result, and leaves durable evidence.

## Phase 19 — Production application weaving and everyday UI

- Start the owner-private Application Fabric socket and compose the live
  registry, broker, Linux discovery, deterministic adapters, and action safety.
- Package the VS Code extension as a VSIX. Add `fam-os connector install vscode`,
  `status`, `update`, and `remove`; connection requires explicit enablement.
- Replace fixed acceptance prompts with capability-driven plan compilation using
  native connectors first, then deterministic OS/tool APIs, AT-SPI, and finally
  restricted screen input.
- Support VS Code editor observation, diagnostics, revision-bound edit preview,
  apply, undo, and save. Persistent edits require disk digest and declared
  test/postcondition verification.
- Compose allowlisted MCP clients. MCP ingress is a permission-filtered Core
  client, never a policy bypass; its action results remain untrusted until
  independently verified.
- Keep accessibility and screen/input disabled by default and show observation,
  action, and privacy scope when enabled.
- Make Console the primary work surface: conversation, context picker, live
  execution spine, preview/approval/deny/cancel/undo, result/citations/evidence,
  escalation, resources, experts, apps, permissions, memory, devices, factory,
  audit, and recovery.
- Preserve the cool-paper identity while replacing the generic dashboard with a
  distinctive fabric execution spine. Bundle open-license fonts and support
  keyboard navigation, responsive layouts, and reduced motion.
- Add authenticated task APIs: `POST /api/v1/tasks`,
  `GET /api/v1/tasks/{id}`, `GET /api/v1/tasks/{id}/events` via SSE,
  `POST /api/v1/tasks/{id}/decision`, and
  `POST /api/v1/tasks/{id}/cancel`.
- Exchange the launcher bootstrap token for an HttpOnly SameSite session; protect
  mutations with Origin and CSRF checks.
- Submit plain Shell text as a task. Retain `/help`, `/context`, `/approve`,
  `/deny`, `/cancel`, with `ask` only as a compatibility alias, and stream
  progress without refresh.
- Let the owner open a folder beneath the home directory, select an exact file
  or folder resource, and inspect bounded list/read evidence in a Tool terminal.
  Exact listings bypass model synthesis; displayed model commands remain inert.
- Add a bounded Core-owned observe/choose/execute/reobserve loop for recursive
  project discovery and deterministic tools. Do not expose a raw browser PTY.

Exit gate: Console or Shell can summarize a project, run a test, and perform an
approved VS Code edit with preview, undo, and deterministic verification.

## Phase 20 — Memory, retrieval, and local adaptation

- Enable bounded ephemeral session memory by default; persistent memory is
  opt-in.
- Let users approve folders/documents with explicit scope, expiry, and allowed
  applications.
- Ground FAM_OS identity and project answers in approved local docs with exact
  citations, preventing fabricated descriptions.
- Expose inspect, correct, export, expire, and delete in Console and Shell;
  deletion removes payloads and issues a durable receipt.
- Adapt only from verified outcomes and prefer derived features over raw prompts.
- Connect frequency, prefetch, context, and escalation prediction to scheduling.
- Expose learned behavior with disable/reset controls and roll back on quality,
  thermal, or policy regression.

Exit gate: repeated workflows improve latency or resource use while every
persistent record and learned behavior is inspectable and removable.

## Phase 21 — Real trusted multi-device fabric

- Run a supervised peer service with persistent identity, manual pairing, and
  mutual TLS; discovery advertises only already trusted devices.
- Persist enrollment, revocation, capability, performance, and privacy policy.
- Send only minimum approved context. Raw prompts, files, and memory require
  explicit scope.
- Integrate local/remote choice into the normal scheduler, Core budget, and
  verification policy.
- Bind remote response to request, plan, expert, and evidence identities; never
  release partial output.
- On disconnect, discard partial state, reconcile global budget, and retry
  locally only with unchanged acceptance.
- Prove final behavior on at least two physical Linux machines; localhost is
  development evidence only.

Exit gate: a trusted remote expert handles a real task, peer loss recovers under
the same verified contract, and unauthorized context is not exposed.

## Phase 22 — Real Expert Factory

- Replace the demonstration classifier with a supervised factory consuming
  verified failure traces and proposing, never automatically starting, training.
- Require approval of capability, dataset, base model, license, resource budget,
  and expected runtime.
- Isolate training behind a `TrainingBackend`; the initial NVIDIA backend uses
  PyTorch, TRL/PEFT LoRA or QLoRA, and bitsandbytes.
- Use official Qwen3-1.7B or its base variant as the first bounded student.
  Laguna or Gemma may propose teacher data, but deterministic or human review is
  mandatory before inclusion.
- Produce immutable train/validation/held-out splits with provenance and leakage
  checks.
- Train only with explicit approval, safe thermal/disk/VRAM state, no foreground
  pressure, and no conflicting inference.
- Evaluate quality, safety, latency, memory, VRAM, and energy against the current
  package; reject policy regressions.
- Convert through pinned digest-verified tooling, sign, install through Expert
  Fabric, canary, automatically roll back regressions, and preserve audit history
  on retirement.
- Keep consumer-workstation large-base pretraining out of scope; deliver
  micro-experts, adapters, distillation, and quantized specialists.

Exit gate: a verified local failure leads to an approved LoRA/QLoRA specialist
that improves held-out results, is selected by FAM, and can be rolled back and
removed.

## Phase 23 — Final release qualification

Current status: clean built-artifact profiles and suites (23.1–23.2) pass from
one wheel in `phase23-required-20260718-01`. Signed installed matrix
`phase23-installed-20260718-11` passes local, application, MCP, memory,
Laguna/Gemma escalation, media, same-host remote, and Factory scenarios,
including restart while awaiting approval, uncertain-action recovery,
candidate-only fault injection, acceptance-independent Factory composition, and
truthful missing-key recovery state. Step 23.3 remains in progress only because
its remote scenario still requires the separate two-physical-host proof from
21.7. Installed matrix `phase23-hardware-20260718-06` completes the independent
CPU-only/full-workstation gate and, together with Run 11, proves live
authoritative Console state. The 24-hour soak, human review, and final signed
fresh-user lifecycle remain open.

- Run clean base, mathematics, verification, media, training, and VS Code install
  matrices; no test depends on undeclared optional software.
- Run unit, contract, architecture, integration, security, hardware, and
  connector suites from built release artifacts.
- Prove installed scenarios: grounded FAM identity, project summary, bounded
  tests, approved persisted VS Code edit, Laguna/Gemma escalation, restart while
  awaiting approval, uncertain-action recovery, memory deletion, media, physical
  remote execution/disconnect, and factory activation/rollback.
- Retain the passing independent 16 GiB CPU-only and full-workstation profile
  matrix as the hardware baseline for the remaining soak and lifecycle runs.
- Run at least 24 hours with inference, connector churn, memory/GPU/low-disk
  pressure, verifier/Ollama crashes, daemon restarts, and update rollback.
- Retain the passing Console authority comparisons across host, cgroup,
  filesystem, NVIDIA, Ollama, encrypted repositories, and recovery mode.
- Complete independent human security review of HTTP, Unix sockets, VS Code,
  MCP, sandboxing, signing, model ownership, memory keys, and peer transport.
  High or critical findings block release.
- Build a signed release candidate and prove fresh-user install, update,
  rollback, recovery, and total removal.

Exit gate: all Phase 23 evidence comes from the installed release and references
no acceptance-only composition. Only then may `MASTER_PLAN.md` be complete.

## Defaults and non-negotiable constraints

- Full local integration comes first; full completion includes physical-device
  fabric and the real Expert Factory.
- Managed Ollama is default, behind a provider boundary.
- Session memory is enabled; persistent indexing is opt-in.
- File, application, remote, and training mutations require explicit scoped
  authority.
- AT-SPI and screen/input are disabled by default.
- Strong models are escalation resources, not default chat models.
- Historical ADRs and handoffs are append-only.
- Every major implementation step creates a handoff.
- No god module or all-purpose integration script is permitted.
