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
from fam_os.core.contracts.result import (
    TASK_RESULT_CONTRACT_VERSION,
    ResultAssurance,
    ResultCitation,
    ResultKind,
    ResultStatus,
    TaskResult,
)
from fam_os.core.contracts.legacy_result import (
    LEGACY_TASK_RESULT_VERSION,
    TaskResult as TaskResultV1Alpha1,
    migrate_task_result_v1alpha1,
)
from fam_os.core.contracts.version import CORE_CONTRACT_VERSION

__all__ = [
    "CORE_CONTRACT_VERSION",
    "TASK_RESULT_CONTRACT_VERSION",
    "LEGACY_TASK_RESULT_VERSION",
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
    "ResultAssurance",
    "ResultCitation",
    "ResultKind",
    "RetryDisposition",
    "StepOutcome",
    "TaskRequest",
    "TaskResult",
    "TaskResultV1Alpha1",
    "migrate_task_result_v1alpha1",
    "TerminalDisposition",
]
