"""Representative bounded master engineering lifecycle state."""

from fam_os.core.engineering import (
    EngineeringLoopBudget,
    EngineeringLoopStage,
    EngineeringLoopState,
)
from tests.contract.schema_engineering_fixtures import NOW


def master_loop_schema_values() -> tuple[object, ...]:
    return (EngineeringLoopState(
        "task-1", "grant-engineering-1", EngineeringLoopStage.VERIFIED, 4,
        EngineeringLoopBudget(100_000, 3600, 100, 10_000_000, 1000, 1_000_000_000, 1000, 20, 4, 0, 3, 1024),
        "repository-evidence-1", "architecture-1", "candidate-1", (),
        ("verification-1",), (), (), (), (), (), (), None, None,
        "a" * 64, NOW,
    ),)
