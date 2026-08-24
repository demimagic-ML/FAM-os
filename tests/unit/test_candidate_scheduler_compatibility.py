import unittest

from fam_os.expert_factory import (
    FactoryEvaluationApproval,
    PairedEvaluationMeasurement,
)
from fam_os.product.candidate_scheduler_compatibility import (
    CandidateSchedulerCompatibilityProbe,
)
from tests.contract.schema_manifest_fixtures import resource_manifest_schema_values


class CandidateSchedulerCompatibilityTests(unittest.TestCase):
    def test_selects_candidate_only_for_declared_capability(self) -> None:
        approval, measurements = _fixture()
        result = CandidateSchedulerCompatibilityProbe().compatible(
            approval=approval, measurements=measurements,
            base_artifact_bytes=3 * 1024**3, adapter_bytes=32 * 1024**2,
        )
        self.assertTrue(result)

    def test_rejects_candidate_that_cannot_fit_approved_capacity(self) -> None:
        approval, measurements = _fixture()
        self.assertFalse(CandidateSchedulerCompatibilityProbe().compatible(
            approval=approval, measurements=measurements,
            base_artifact_bytes=20 * 1024**3, adapter_bytes=1,
        ))


def _fixture() -> tuple[
    FactoryEvaluationApproval, tuple[PairedEvaluationMeasurement, ...],
]:
    values = resource_manifest_schema_values()
    approval = next(
        item for item in values if isinstance(item, FactoryEvaluationApproval)
    )
    measurements = tuple(
        item for item in values if isinstance(item, PairedEvaluationMeasurement)
    )
    return approval, measurements


if __name__ == "__main__":
    unittest.main()
