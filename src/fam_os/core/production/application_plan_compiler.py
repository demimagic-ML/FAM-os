"""Compile immutable plans directly from live Application Fabric capabilities."""

from fam_os.applications import (
    CapabilityKind,
    WORKSPACE_PATCH_CAPABILITY,
    WORKSPACE_RESTORE_CAPABILITY,
    WORKSPACE_RETRIEVE_CAPABILITY,
)
from fam_os.core.contracts import (
    ExecutionPlan,
    PlanStep,
    PlanStepKind,
    PlanTransition,
    StepOutcome,
    TerminalDisposition,
)


class ApplicationPlanCompiler:
    def compile(
        self, request_id, route, entries, verification_required,
        deterministic_parameters=False,
    ):
        if not entries:
            raise ValueError("application plan requires live capabilities")
        steps = []
        app_steps = []
        for entry in entries:
            if not entry.available:
                raise ValueError("application plan capability is unavailable")
            if entry.capability.kind is CapabilityKind.OBSERVATION:
                step = PlanStep(
                    f"observe-{len(app_steps) + 1}", PlanStepKind.OBSERVE,
                    entry.capability.display_name, (entry.capability_id,),
                )
                steps.append(step)
                app_steps.append(step)
        internal = tuple(
            capability for capability in route.required_capabilities
            if capability.startswith("core.intent.")
        )
        inference = PlanStep(
            "inference", PlanStepKind.INFERENCE,
            (
                "Use deterministic action parameters"
                if deterministic_parameters else
                "Generate an application candidate"
            ),
            internal,
        )
        steps.append(inference)
        app_steps.append(inference)
        for entry in entries:
            if entry.capability.kind is CapabilityKind.ACTION:
                sequence = len(tuple(
                    item for item in steps if item.kind is PlanStepKind.PREPARE_ACTION
                )) + 1
                prepare = PlanStep(
                    f"prepare-action-{sequence}", PlanStepKind.PREPARE_ACTION,
                    f"Preview {entry.capability.display_name}", (entry.capability_id,),
                )
                confirm = PlanStep(
                    f"confirm-action-{sequence}", PlanStepKind.CONFIRM_ACTION,
                    f"Approve {entry.capability.display_name}", (entry.capability_id,),
                )
                execute = PlanStep(
                    f"execute-action-{sequence}", PlanStepKind.EXECUTE_ACTION,
                    entry.capability.display_name, (entry.capability_id,),
                    entry.capability.postcondition_ids,
                )
                steps.extend((prepare, confirm, execute))
                app_steps.extend((prepare, confirm, execute))
                if entry.capability_id in {
                    WORKSPACE_PATCH_CAPABILITY, WORKSPACE_RESTORE_CAPABILITY,
                } and any(
                    item.capability_id == WORKSPACE_RETRIEVE_CAPABILITY
                    for item in entries
                ):
                    reobserve = PlanStep(
                        f"reobserve-action-{sequence}", PlanStepKind.OBSERVE,
                        "Re-observe patched workspace files",
                        (WORKSPACE_RETRIEVE_CAPABILITY,),
                    )
                    steps.append(reobserve)
                    app_steps.append(reobserve)
        has_actions = any(
            item.capability.kind is CapabilityKind.ACTION for item in entries
        )
        verified = verification_required or has_actions
        if verified:
            acceptance_ids = (
                tuple(dict.fromkeys(
                    condition
                    for entry in entries
                    if entry.capability.kind is CapabilityKind.ACTION
                    for condition in entry.capability.postcondition_ids
                ))
                if has_actions else ("acceptance.application.grounded",)
            )
            verify = PlanStep(
                "verify", PlanStepKind.VERIFY,
                "Verify deterministic application result",
                acceptance_ids=acceptance_ids,
            )
            steps.append(verify)
            app_steps.append(verify)
        terminals = _terminals()
        steps.extend(terminals)
        transitions = _linear_transitions(tuple(app_steps), terminals)
        return ExecutionPlan(
            f"plan-{request_id}", request_id, route, app_steps[0].step_id,
            tuple(steps), transitions, verified,
        )


def _terminals():
    return (
        PlanStep(
            "release", PlanStepKind.FINALIZE, "Release accepted result",
            terminal_disposition=TerminalDisposition.RELEASE,
        ),
        PlanStep(
            "withhold", PlanStepKind.FINALIZE, "Withhold unapproved result",
            terminal_disposition=TerminalDisposition.WITHHOLD,
        ),
        PlanStep(
            "fail", PlanStepKind.FINALIZE, "Fail safely",
            terminal_disposition=TerminalDisposition.FAIL,
        ),
    )


def _linear_transitions(steps, terminals):
    release, withhold, fail = terminals
    transitions = []
    for index, step in enumerate(steps):
        target = steps[index + 1].step_id if index + 1 < len(steps) else release.step_id
        transitions.append(PlanTransition(step.step_id, StepOutcome.SUCCEEDED, target))
        transitions.append(PlanTransition(step.step_id, StepOutcome.CANCELLED, withhold.step_id))
        transitions.append(PlanTransition(step.step_id, StepOutcome.FAILED, fail.step_id))
        if step.kind in {
            PlanStepKind.OBSERVE, PlanStepKind.PREPARE_ACTION,
            PlanStepKind.EXECUTE_ACTION, PlanStepKind.VERIFY,
        }:
            transitions.append(PlanTransition(
                step.step_id, StepOutcome.UNAVAILABLE, withhold.step_id,
            ))
        if step.kind is PlanStepKind.CONFIRM_ACTION:
            transitions.extend((
                PlanTransition(step.step_id, StepOutcome.DENIED, withhold.step_id),
                PlanTransition(step.step_id, StepOutcome.EXPIRED, withhold.step_id),
            ))
    return tuple(transitions)
