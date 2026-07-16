"""Bounded deterministic test execution through a real Core plan."""

from pathlib import Path

from fam_os.adapters.linux.bounded_command import (
    BoundedCommandPolicy, BoundedSubprocessRunner,
)
from fam_os.adapters.linux.tools import (
    AllowlistedToolAdapter, ToolCapabilitySpec, ToolOutputKind,
)
from fam_os.application_acceptance.contracts import (
    IntegrationLevel, ScenarioEvidence,
)
from fam_os.application_acceptance.core_session import AcceptanceCoreSession, plan_factory
from fam_os.application_acceptance.metrics import OperationMeter
from fam_os.core.contracts import (
    PlanStep, PlanStepKind, PlanTransition, StepOutcome, TerminalDisposition,
)
from fam_os.core.lifecycle import PlanEvidenceKind, PlanEvidenceReference


TEST_CAPABILITY = "linux.tool.python_unittest.application_actions"
TEST_NAME = (
    "tests.unit.test_application_permissions_actions.ActionContractTests."
    "test_verified_action_requires_passing_postconditions"
)


class BoundedTestWorkflow:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        self.meter = OperationMeter()
        self.core_snapshot = None

    def run(self, request_id, prompt):
        session = AcceptanceCoreSession.start(
            request_id, prompt, self._plan(request_id), (),
        )
        result = self.meter.measure(
            f"{request_id}-tool", IntegrationLevel.DETERMINISTIC, TEST_CAPABILITY,
            lambda: self._adapter().invoke(TEST_CAPABILITY, {}),
        )
        outcome = StepOutcome.SUCCEEDED if result.succeeded else StepOutcome.FAILED
        reference = PlanEvidenceReference(
            f"test-evidence-{request_id}",
            PlanEvidenceKind.VERIFICATION_PASS if result.succeeded
            else PlanEvidenceKind.FAILED_ATTEMPT,
            TEST_CAPABILITY,
        )
        advanced = session.lifecycle.advance(
            session.plan_instance_id, 0, outcome, (reference,),
        )
        if advanced.rejection is not None:
            raise RuntimeError("test lifecycle transition failed")
        self.core_snapshot = advanced.snapshot
        if not result.succeeded:
            return ScenarioEvidence(
                request_id, False, False, False, "", (TEST_CAPABILITY,), (), (),
                tuple(self.meter.measurements), failure_code=result.error_code,
            )
        content = (
            f"Verified test passed: {TEST_NAME}.\n"
            f"Capability used: {TEST_CAPABILITY}. Provider: /usr/bin/python3."
        )
        return ScenarioEvidence(
            request_id, True, True, False, content, (TEST_CAPABILITY,), (), (),
            tuple(self.meter.measurements),
        )

    def _adapter(self):
        spec = ToolCapabilitySpec(
            TEST_CAPABILITY, Path("/usr/bin/python3"),
            ("-m", "unittest", TEST_NAME), (),
            {"type": "object", "additionalProperties": False},
            ToolOutputKind.TEXT, self.root,
            (("PYTHONPATH", f"{self.root / 'src'}:{self.root}"),),
        )
        runner = BoundedSubprocessRunner(BoundedCommandPolicy(
            timeout_seconds=30, maximum_stdout_bytes=65_536,
            maximum_stderr_bytes=65_536,
        ))
        return AllowlistedToolAdapter((spec,), runner)

    @staticmethod
    def _plan(request_id):
        steps = (
            PlanStep(
                "test", PlanStepKind.DETERMINISTIC_TOOL, "Run one bounded test",
                (TEST_CAPABILITY,), ("process.exit_zero",),
            ),
            PlanStep("release", PlanStepKind.FINALIZE, "Release test result",
                     terminal_disposition=TerminalDisposition.RELEASE),
            PlanStep("fail", PlanStepKind.FINALIZE, "Withhold failed test",
                     terminal_disposition=TerminalDisposition.FAIL),
        )
        transitions = (
            PlanTransition("test", StepOutcome.SUCCEEDED, "release"),
            PlanTransition("test", StepOutcome.FAILED, "fail"),
        )
        return plan_factory(
            f"plan-{request_id}", request_id, (TEST_CAPABILITY,),
            steps, transitions,
        )
