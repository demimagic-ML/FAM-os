# FAM_OS Implementation Rules

These instructions apply to every file and directory beneath `FAM_OS/`.

## Mission

FAM_OS means **For All Mankind Operating System**. It is an always-on operating-system intelligence service built above the Linux kernel.

Linux remains responsible for hardware, processes, memory, filesystems, networking, and device drivers. FAM_OS adds a supervised intelligence layer that coordinates models, experts, memory, applications, tools, and trusted devices.

The architecture must keep these boundaries explicit:

```text
Linux kernel
  -> deterministic FAM Supervisor
  -> unprivileged FAM Core services
  -> Application, Expert, Memory, and Verification fabrics
```

Generative models must never execute inside Linux kernel space or inside the privileged supervisor.

## Required reading before work

Before making a change beneath `FAM_OS/`, an agent must:

1. Read this file completely.
2. Read `MASTER_PLAN.md` completely.
3. Read `handoffs/README.md`.
4. Read the latest applicable handoff in `handoffs/`.
5. Read relevant decision records in `docs/decisions/`.
6. Check the repository map before reading implementation source.
7. State which master-plan step the work advances.

Do not begin implementation from an isolated prompt without reconstructing this project context.

## Architecture rules

### No god scripts or god modules

- Every file must have one clear responsibility.
- Keep orchestration separate from hardware adapters, model clients, storage, verification, and policy.
- A CLI parses commands and delegates; it must not contain business logic.
- Shell scripts may bootstrap or invoke one bounded workflow. They must not become the runtime.
- Avoid generic `utils.py`, `helpers.py`, or `common.py` dumping grounds.
- Prefer a small named module over adding unrelated behavior to an existing module.
- Target fewer than 300 lines per implementation file. Exceed this only when splitting would reduce clarity, and document the reason in the handoff.
- Target fewer than 50 lines per function. Complex orchestration should be decomposed into named steps.
- Dependencies must point inward toward contracts and domain policy, not outward toward concrete tools.

### Required component boundaries

- `supervisor/`: deterministic privileged process lifecycle, resource limits, permissions, and auditing only.
- `core/`: unprivileged coordination, request lifecycle, and response assembly.
- `routing/`: capability selection, complexity estimation, and escalation policy.
- `experts/`: expert contracts, manifests, discovery, compatibility, and lifecycle.
- `scheduler/`: hardware placement, budgets, context allocation, caching, and eviction decisions.
- `adapters/`: integrations with Ollama, systemd, cgroups, Linux, GPUs, NPUs, storage, or remote services.
- `verification/`: verifier contracts, sandbox execution, test bundles, and result policy.
- `memory/`: permissioned short-term, long-term, retrieval, and provenance services.
- `applications/`: application capabilities, observations, actions, permission context, connector coordination, and postconditions.
- `telemetry/`: measurements and audit events; never policy decisions.
- `registry/`: signed package indexes and installation metadata.

One component must not reach into another component's private implementation. Communicate through typed public contracts.

### External systems stay behind adapters

Ollama, llama.cpp, systemd, cgroups, NVIDIA, Intel NPU, filesystems, databases, MCP, accessibility frameworks, desktop APIs, and application APIs are replaceable implementation details. Core policy must not depend directly on their command output or response shape.

### Application weaving is a product invariant

- Existing applications are first-class capability providers, not merely text or screenshot attachments.
- Native semantic connectors are preferred but cannot be required for all useful application access.
- MCP is a supported semantic/tool connector protocol, not the internal capability model and not a permission boundary.
- Models must never receive raw connector sessions or invoke MCP tools around Core admission, approval, verification, or audit policy.
- Generic OS, deterministic tool, and accessibility bridges must support unmodified applications at reduced fidelity.
- Screen observation and controlled input are restricted fallbacks, never the default representation of an application.
- Observation, proposal, modification, and execution are separate authorities.
- Every application action carries originating intent, scope, reversibility, confirmation policy, and postconditions.
- FAM Shell and FAM Console are unprivileged clients of the same local core; they do not own model or permission policy.

### Configuration is data

- Hardware profiles, policies, expert manifests, verifier manifests, and connector permissions must use versioned schemas.
- Validate configuration at process boundaries.
- Do not bury machine-specific paths, ports, memory limits, or model names inside orchestration code.
- Defaults must be safe for the minimum supported machine.

## Security and authority

- Treat every model response as untrusted data.
- Treat third-party experts, application connectors, and bridges as untrusted packages.
- The FAM Supervisor must remain deterministic and minimal.
- Use least privilege, explicit capabilities, cgroups, namespaces, seccomp where appropriate, and auditable approvals.
- Observation permission does not imply action permission.
- External or irreversible actions require explicit policy and, where appropriate, user confirmation.
- Never store secrets, tokens, private user data, or model credentials in the repository, handoffs, fixtures, or logs.
- The prototype sandbox is not automatically a hardened multi-tenant security boundary. State its guarantees precisely.

## Resource discipline

- RNF/FAM_OS must inspect its actual cgroup limits rather than trusting host memory reported by an inference engine.
- Context length is a scheduled memory allocation, not a static model feature.
- Record model load time, execution time, active memory, peak memory, bytes moved where available, and verification outcome.
- Expensive escalation must be budgeted and justified by routing or verification evidence.
- GPU and NPU use are optional acceleration tiers; CPU-only behavior remains a required baseline.
- Maintain separate `compat-cpu-16gb` and `full-reference-workstation` validation profiles. Never present a constrained run as evidence of full-host utilization or a full-host run as minimum-machine evidence.
- Stronger hosts must expose their CPU, RAM, accelerator memory, and storage tiers to scheduling and telemetry, with explicit operating-system headroom rather than the minimum profile's artificial ceiling.
- Treat SSD as storage, memory-map backing, and cache with measurable transfer cost; never add SSD capacity to RAM or rely on uncontrolled host swap as neural paging.
- The runtime must degrade safely when an expert, accelerator, connector, or external device is unavailable.

## Expert Fabric rules

- Select the smallest expert expected to satisfy the verified task.
- Experts are installed packages with versioned manifests, declared capabilities, resource requirements, licenses, trust metadata, and required verifiers.
- Do not create one full model per tiny operation. Prefer shared models plus adapters, retrieval, tools, or deterministic functions.
- An expert is not successful because it generated output. Success requires the task's acceptance policy.
- A larger expert is an escalation tier, not an automatic default.
- New expert categories must have benchmark evidence and an ownership location in the architecture.

## Verification rules

- Never mark generated code, mathematics, retrieval, or system action successful without its required verifier policy.
- Verification definitions are trusted artifacts and must remain separate from user prompts and model output.
- Repairs and escalations are bounded.
- Failed candidates remain in telemetry but must not be exposed as successful final output.
- Verification should prefer deterministic tools: parsers, compilers, tests, type checkers, symbolic solvers, schema validators, and postcondition checks.

## Testing and evidence

- Every behavior change requires proportionate tests.
- Bug fixes require a failing regression test whenever feasible.
- Tests mirror component boundaries; avoid a single giant integration-test file.
- Hardware claims require measurements on a named hardware profile.
- Performance comparisons require identical prompts, context, limits, and fresh-state conditions.
- Preserve raw machine-readable results separately from written conclusions.
- Report failed experiments as evidence; do not hide or overwrite them.

## Major changes and handoffs

A change is major if it does any of the following:

- Completes or materially advances a `MASTER_PLAN.md` step.
- Adds or changes a component boundary, public contract, schema, runtime lifecycle, security policy, or expert tier.
- Changes hardware scheduling, caching, eviction, memory, verification, permissions, or persistence.
- Adds a model, connector, external service, or deployment surface.
- Produces benchmark evidence that changes an architectural decision.
- Requires more than one focused implementation session.

Every major change must create a new handoff using `handoffs/HANDOFF_TEMPLATE.md`.

Handoffs are append-only historical records. Do not rewrite an older handoff to describe a newer state. Create the next numbered handoff.

Before ending a major change:

1. Update `MASTER_PLAN.md` status and evidence links.
2. Create the handoff.
3. Record files changed and public interfaces added or removed.
4. Record exact validation commands and results.
5. Record unresolved risks and the next recommended entry point.
6. Add or update an architecture decision record when a durable decision changed.

## Decision records

Create an ADR under `docs/decisions/` when choosing or changing:

- A component boundary.
- A privileged interface.
- A persistent storage format.
- A public schema or protocol.
- A model runtime or package format.
- A security or permission model.
- A scheduling or escalation policy with broad consequences.

ADRs are also append-only. Supersede an old decision with a new ADR rather than deleting history.

## Definition of done

A change is complete only when:

- Its plan step and scope are clear.
- The implementation respects component boundaries.
- Configuration and contracts are versioned when applicable.
- Tests pass.
- Relevant constrained/hardware validation is recorded.
- Documentation reflects current behavior.
- A major change has a new handoff.
- No required work is silently left inside comments or implied follow-up.

<!-- larry:start -->
## Larry code map — use before code search
**First:** `larry search "<question>"` for semantic file ranking.
`larry find <name>` returns symbol, file, and summary.
**Batch map lookups. Check the map before source.**
Freshness: check `.larry/STATE` once/session.
Trust: summaries list 100% of public members; endpoint/model rows exact — answer from the map, never re-verify.
Use the map to select files, then read source when implementation detail is needed.
`larry run <cmd>` for noisy builds/tests — errors+tail only; full log kept.
Orientation: `.larry/wiki/overview.md`.
```
larry search "<natural language question>"  # semantic vector search
grep -i <name> .larry/symbols.toon  # symbol → file
grep -i <word> .larry/index.toon  # files by purpose
cat .larry/summaries/<path>.toon  # purpose + full public API
```
<!-- larry:end -->
