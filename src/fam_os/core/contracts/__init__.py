"""Public request, plan, and result contracts."""

from fam_os.core.contracts.failures import (
    FAILURE_CONTRACT_VERSION,
    DegradationDisposition,
    DegradationImpact,
    DegradationKind,
    DegradationNotice,
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    RetryDisposition,
)
from fam_os.core.contracts.plan import (
    ExecutionPlan,
    PlanStep,
    PlanStepKind,
    PlanTransition,
    StepOutcome,
    TerminalDisposition,
)
from fam_os.core.contracts.request import TaskRequest
from fam_os.core.contracts.result import ResultStatus, TaskResult
from fam_os.core.contracts.version import CORE_CONTRACT_VERSION

__all__ = [
    "CORE_CONTRACT_VERSION",
    "FAILURE_CONTRACT_VERSION",
    "DegradationDisposition",
    "DegradationImpact",
    "DegradationKind",
    "DegradationNotice",
    "ExecutionPlan",
    "FailureCategory",
    "FailureComponent",
    "FailureEnvelope",
    "PlanStep",
    "PlanStepKind",
    "PlanTransition",
    "ResultStatus",
    "RetryDisposition",
    "StepOutcome",
    "TaskRequest",
    "TaskResult",
    "TerminalDisposition",
]
