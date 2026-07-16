# Handoff 0013: Core execution-plan contracts

**Date:** 2026-07-16  
**Plan step:** Phase 2.1  
**Status:** Complete  
**Previous handoff:** `0012-application-fabric-contracts.md`

## Objective

Complete the provider-neutral request, route, capability, execution-plan, and final-result boundary without replacing or changing the measured Phase 1 verified-code orchestration path.

## Scope completed

- Added the `fam.core/v1alpha1` Python contract-family marker to Core request, plan, and final-result types.
- Added the `fam.routing/v1alpha1` marker to routing request and result types.
- Added an immutable provider-neutral execution-plan graph.
- Added typed observation, inference, deterministic-tool, action-preparation, confirmation, action-execution, verification, and finalization steps.
- Added success, failure, denial, unavailable, and cancelled transition outcomes.
- Added release, withhold, and fail terminal dispositions.
- Required one known entry, unique step IDs, known transition targets, deterministic source/outcome selection, reachability, and acyclic graphs.
- Required every non-final step to transition and every final step to stop.
- Required each routed capability to be covered by at least one plan step.
- Required relevant steps to name capabilities and verification/action steps to name acceptance checks.
- Required every release terminal to have an inbound transition.
- Required verified release branches to follow successful accepted evidence while preserving ordinary non-verified response release.
- Represented the current economical, repair, escalation, verification, release, and withhold flow as an execution-plan test without changing the live use case.
- Added plan and evidence references to `TaskResult`.
- Required verified final results to identify passing evidence.
- Required withheld and failed results to carry a reason and no content.
- Linked Phase 1 verified results to the exact final passing verification ID.
- Required `VerifiedExecutionOutcome` to confirm that the referenced evidence belongs to the final passing attempt.
- Normalized and deduplicated routing capability requirements.
- Added ADR 0014 and Core contract-family documentation.
- Marked Master Plan step 2.1 complete and advanced the immediate step to 2.2.

## Explicitly not completed

- The new execution plan is not executed by a runtime state machine.
- `VerifiedCodeExecution` was not replaced or restructured.
- No mutable plan state, event log, authorization evaluation, deadline, cancellation, recovery, or resumption behavior was implemented.
- No serialized schema, decoder, encoder, compatibility migration, or stable external protocol was added.
- No hardware/resource schema was added; that is Phase 2.2.
- No model, connector, application, service, or machine setting was changed.

## Architecture and decisions

ADR 0014 chooses a directed acyclic transition graph instead of a flat command list or a cyclic workflow. Repair and escalation bounds become explicit nodes, so a plan cannot hide an unbounded loop. A `(source step, outcome)` pair selects at most one target, which preserves deterministic transition policy while allowing multiple explicit outcomes.

Plan steps carry capability and acceptance identifiers rather than model names, shell commands, VS Code types, MCP types, or provider payloads. Resolution of experts, applications, tools, verifiers, and hardware remains with their owning components.

Release safety has two layers. A plan that requires verification cannot direct release from an unsuccessful or evidence-free step. A `TaskResult` cannot claim verified content without evidence IDs. The existing verified-code outcome additionally proves that released content and the referenced evidence both belong to the final passing attempt.

Not every FAM response claims deterministic verification. `ExecutionPlan.verification_required=False` permits a normal successful inference to reach release, producing a `completed` rather than falsely `verified` result.

The plan is a static contract only. Phase 4.3 owns the mutable state machine and must not be smuggled into this Phase 2 change.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/contracts/version.py` | Core Python contract-family marker |
| `src/fam_os/core/contracts/plan.py` | Typed execution steps, transitions, terminals, and graph invariants |
| `src/fam_os/core/contracts/request.py` | Core version marker on admitted requests |
| `src/fam_os/core/contracts/result.py` | Plan/evidence references and stronger release invariants |
| `src/fam_os/core/contracts/__init__.py` | Public plan and version exports |
| `src/fam_os/routing/contracts.py` | Routing marker and normalized capability invariants |
| `src/fam_os/routing/__init__.py` | Public routing marker export |
| `src/fam_os/core/execution/use_case.py` | Passing verification reference on verified results |
| `src/fam_os/core/execution/contracts.py` | Released-evidence-to-final-attempt check |
| `tests/unit/test_core_plan_contracts.py` | Plan graph, bounded flow, release, cycle, reachability, and coverage tests |
| `tests/unit/test_core_contracts.py` | Version, evidence, and failure-reason tests |
| `tests/unit/test_routing_contracts.py` | Routing version and capability normalization tests |
| `tests/unit/test_verified_code_execution.py` | Passing evidence linkage regression assertion |
| `docs/protocols/CORE_CONTRACTS.md` | Contract-family and execution-plan reference |
| `docs/decisions/0014-core-execution-plan-contracts.md` | Execution-plan architecture decision |
| `src/fam_os/core/README.md` | Core ownership and plan-state boundary |
| `src/fam_os/routing/README.md` | Routing family ownership and version |
| `MASTER_PLAN.md` | Phase 2.1 completion evidence and Phase 2.2 entry point |
| `README.md` | Current implementation and next-step status |
| `handoffs/README.md` | Handoff sequence entry |
| `handoffs/0013-core-execution-plan-contracts.md` | This implementation record |

## Public interfaces

- `CORE_CONTRACT_VERSION`
- `ROUTING_CONTRACT_VERSION`
- `PlanStepKind`
- `StepOutcome`
- `TerminalDisposition`
- `PlanStep`
- `PlanTransition`
- `ExecutionPlan`
- `TaskRequest.contract_version`
- `RoutingRequest.contract_version`
- `RoutingResult.contract_version`
- `TaskResult.plan_id`
- `TaskResult.evidence_ids`
- `TaskResult.contract_version`

Existing `TaskRequest`, routing, Phase 1 execution, and `TaskResult` meanings remain provider neutral. Verified `TaskResult` construction is intentionally stricter because evidence is now mandatory.

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_core_contracts \
  tests.unit.test_core_plan_contracts \
  tests.unit.test_routing_contracts \
  tests.unit.test_verified_code_execution -v
```

Result: all 27 focused request, routing, plan, final-result, and verified-orchestration tests passed in 0.001 seconds; 0 failures.

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
```

Result: all 134 FAM_OS tests passed in 0.032 seconds; 0 failures. The previous suite contained 123 tests.

```bash
python3 -m compileall -q src tools tests
```

Result: completed successfully.

```bash
rg -n "Ollama|WorkspaceEdit|MCP|vscode|subprocess|systemd" \
  src/fam_os/core/contracts src/fam_os/routing/contracts.py
```

Result: no provider, connector, process, or service implementation dependency was found.

`core/contracts/plan.py` is 235 lines and the focused plan test is 195 lines. Functions remain below the repository's 50-line target, and no runtime orchestration was added to the contract module.

## Evidence and artifacts

- `docs/protocols/CORE_CONTRACTS.md`
- `docs/decisions/0014-core-execution-plan-contracts.md`
- `tests/unit/test_core_plan_contracts.py`
- `tests/unit/test_verified_code_execution.py`
- `docs/protocols/APPLICATION_CONTRACTS.md`
- Phase 1 behavior decision: `docs/decisions/0008-verified-code-orchestration-boundary.md`

## Known limitations and risks

- `v1alpha1` markers identify Python contract families, not stable wire schemas.
- The plan describes transitions but has no runtime state, event sequence, timestamps, checkpoint, or replay format.
- Outcome completeness is policy-specific; the contract does not require every possible outcome from every step.
- Parallel/fan-out execution is not represented because one source/outcome selects one target.
- Bounded retries are unrolled and could make large generated plans verbose.
- Capability and acceptance identifiers are syntactic strings until registries and serialized schemas validate namespaces.
- Final-result evidence IDs are linked to trusted objects in the Phase 1 path, but a future cross-process decoder must prevent forged evidence references.
- Ordinary `completed` content is intentionally not labeled verified.
- Application authorization and action postcondition matching remain Phase 4 policy.

## Operational notes

This change is domain contracts, documentation, and in-memory tests only. It started no service, invoked no model, changed no connector, and performed no machine operation.

## Recommended next entry point

Begin Phase 2.2. Define separate versioned host-inventory and effective-resource-budget schemas. Represent CPU topology/allocation, physical and cgroup RAM, explicit OS headroom, GPU identity/VRAM/placement allowance, SSD/cache/I/O budgets, swap policy, current pressure, and validation-profile identity. Preserve the `compat-cpu-16gb` versus `full-reference-workstation` distinction and do not generalize the live benchmark harness until those schemas pass compatibility tests.
