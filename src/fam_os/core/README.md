# Core ownership

Owns the provider-neutral request lifecycle, final release decision, and application use cases.

Core request, execution-plan, and final-result Python contracts use the `fam.core/v1alpha1` family marker. `contracts/plan.py` defines an immutable transition graph with typed steps, outcome-selected transitions, capability coverage, acceptance checks, and release/withhold/fail terminals.

It may depend on public component contracts. It must not call Ollama, systemd, cgroups, devices, or shell commands directly. Concrete orchestration moves here only after those dependencies have ports.

`ingress/` owns the permission-filtered client catalog and the only gateway from
local UI/API/MCP surfaces into request admission and an admitted task executor.
Adapters may call its public port but cannot skip admission or construct verified
results. See `docs/protocols/MCP_INGRESS_SERVER.md` and ADR 0042.

Inference requests own provider-neutral generation controls and call `InferenceRuntime`. Prompts, routing, repair, escalation, verification, and result release remain Core or component policy rather than adapter behavior.

Core sends candidates through the configured `Verifier` port and consumes `VerificationReport`; it never receives trusted test bundles or calls Bubblewrap directly.

`core/execution` owns the verified code application use case. Prompt construction, one-attempt execution, scheduler-selected placement execution, bounded transition policy, internal attempt evidence, and terminal release assembly are separate modules. `VerifiedCodeExecution` may coordinate their public contracts, but it cannot select evictions, inspect provider responses, or define verifier tests.

`TaskResult` is the user-facing release boundary. Failed candidates may remain in `VerifiedExecutionOutcome.attempts` for trusted telemetry and debugging, but a withheld or failed `TaskResult` never contains candidate content.

Verified `TaskResult` content must reference evidence, and the Phase 1 code path now links it to the final passing verification. The generic `ExecutionPlan` does not yet replace `VerifiedCodeExecution`; Phase 4 owns the state-machine implementation. Read `docs/protocols/CORE_CONTRACTS.md` and ADR 0014 first.

Final failed results use `fam.failure/v1alpha1` structured failures, and degraded paths use explicit impact and continue/confirm/withhold dispositions. Raw provider exceptions are not final reasons. Read `docs/protocols/FAILURE_DEGRADATION_CONTRACTS.md` and ADR 0017.

`core/activation` is a non-releasing measurement use case for Phase 1 parity. It records route, placement, loaded-model, inference, and unverified candidate evidence but deliberately has no `TaskResult`; it must not be used as an answer path.

Public Core roots are serialized only through `fam_os.schemas`, whose exact `v1alpha1` policy rejects unknown or missing fields before Core domain construction. Read `docs/protocols/SERIALIZED_SCHEMA_COMPATIBILITY.md` and ADR 0018.

Phase 4.1 adds `core/admission`: trusted authority lookup, exact principal/session
binding, mandatory authority expiry/revocation checks, least-privilege effective
capabilities, atomic single-use request IDs, and structured prompt-free rejection.
It has no runtime or external-boundary imports. Read
`docs/protocols/CORE_REQUEST_ADMISSION.md` and ADR 0031.

Phase 4.2 adds `core/routing`: only admitted requests enter, stale permission is
rejected before the call, the router sees no identity/authority fields, returned
capabilities must preserve the exact effective tuple, and provider/incompatible
failures become safe structured envelopes. Read
`docs/protocols/CORE_ROUTING_LIFECYCLE.md` and ADR 0032.

Phase 4.3 adds `core/lifecycle`: exact request/route/capability binding, immutable
plan snapshots, append-only replay-validated events, optimistic revision checks,
declared-edge-only transitions, and absorbing release/withhold/fail terminals.
The state machine invokes no provider. Read
`docs/protocols/CORE_PLAN_LIFECYCLE.md` and ADR 0033.

Phase 4.4 adds authorized application-backed `OBSERVE` and `PREPARE_ACTION`
states over narrow fake-friendly ports. Core binds the original admission and
expiry, checks exact application grant scope, keeps observe/propose/modify powers
separate, persists only typed evidence references, and exposes no action
execution method. Read `docs/protocols/CORE_APPLICATION_STEPS.md` and ADR 0034.

Phase 4.5 adds replay-safe `CONFIRM_ACTION` transitions. Approval, denial, and
permission expiry bind to the exact proposal/grant/principal/revision context,
use explicit `succeeded`/`denied`/`expired` edges, and persist bounded references
without executing the action. Read
`docs/protocols/CORE_CONFIRMATION_TRANSITIONS.md` and ADR 0035.

Phase 4.6 adds replay-safe, policy-budgeted transitions into distinct unrolled
repair and escalation inference steps. Failed and next-attempt identities remain
reference-only, capabilities remain exact, and no expert is invoked. Read
`docs/protocols/CORE_ATTEMPT_TRANSITIONS.md` and ADR 0036.

Phase 4.7 adds replay-safe cancellation, trusted-deadline timeout, and typed
degradation through declared plan edges with reference-only evidence. Read
`docs/protocols/CORE_CONTROL_TRANSITIONS.md` and ADR 0037.

Phase 4.8 adds registry-backed terminal result policy: only release terminals can
release, verified plans require candidate-linked passing acceptance, blocking
degradation still withholds, and all non-release paths remain content-free. Read
`docs/protocols/CORE_FINAL_RESULT_POLICY.md` and ADR 0038.
