"""Teacher, distillation, adapter, and evaluation pipeline contracts."""

from dataclasses import dataclass

FACTORY_PIPELINE_CONTRACT_VERSION = "fam.factory.pipeline/v1alpha1"


@dataclass(frozen=True, slots=True)
class TeacherDataset:
    dataset_id: str
    teacher_model_ref: str
    example_count: int
    examples_sha256: str
    license_id: str


@dataclass(frozen=True, slots=True)
class DistillationPlan:
    plan_id: str
    dataset: TeacherDataset
    student_interface_id: str
    maximum_epochs: int
    held_out_fraction: float

    def __post_init__(self) -> None:
        if self.maximum_epochs <= 0 or not 0 < self.held_out_fraction < .5:
            raise ValueError("distillation plan bounds are invalid")


@dataclass(frozen=True, slots=True)
class AdapterTrainingPlan:
    adapter_id: str
    base_model_ref: str
    target_capability_id: str
    rank: int
    trainable_parameter_count: int


@dataclass(frozen=True, slots=True)
class EvaluationPlan:
    evaluation_id: str
    acceptance_id: str
    held_out_dataset_sha256: str
    minimum_quality: float
    regression_baseline_id: str

    def __post_init__(self) -> None:
        if not 0 < self.minimum_quality <= 1:
            raise ValueError("evaluation minimum quality must be normalized")
