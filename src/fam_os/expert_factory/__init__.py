"""Evidence-driven local Expert Factory."""

from fam_os.expert_factory.discovery import (
    EXPERT_DISCOVERY_CONTRACT_VERSION, FailureTrace, FailureTraceCluster,
    MissingCapabilityProposal, cluster_failures,
)
from fam_os.expert_factory.pipeline import (
    FACTORY_PIPELINE_CONTRACT_VERSION, AdapterTrainingPlan, DistillationPlan,
    EvaluationPlan, TeacherDataset,
)
from fam_os.expert_factory.training import (
    FACTORY_TRAINING_CONTRACT_VERSION, LabeledExample, TokenWeight,
    TrainedMicroExpert, train_micro_expert,
)
from fam_os.expert_factory.objective import (
    FACTORY_OBJECTIVE_CONTRACT_VERSION, HardwareObjectiveWeights,
    HardwareTrainingMetrics, hardware_objective,
)
from fam_os.expert_factory.quantization import FACTORY_QUANTIZATION_CONTRACT_VERSION, QuantizedVariant
from fam_os.expert_factory.release import FACTORY_RELEASE_CONTRACT_VERSION, PublishedExpertPackage
from fam_os.expert_factory.regression import FACTORY_REGRESSION_CONTRACT_VERSION, RegressionGateResult
from fam_os.expert_factory.lifecycle import FACTORY_LIFECYCLE_CONTRACT_VERSION, FactoryLifecycleReport

__all__ = [
    "EXPERT_DISCOVERY_CONTRACT_VERSION", "FailureTrace", "FailureTraceCluster",
    "MissingCapabilityProposal", "cluster_failures",
    "FACTORY_PIPELINE_CONTRACT_VERSION", "AdapterTrainingPlan", "DistillationPlan",
    "EvaluationPlan", "TeacherDataset", "FACTORY_TRAINING_CONTRACT_VERSION",
    "LabeledExample", "TokenWeight", "TrainedMicroExpert", "train_micro_expert",
    "FACTORY_OBJECTIVE_CONTRACT_VERSION", "HardwareObjectiveWeights",
    "HardwareTrainingMetrics", "hardware_objective", "FACTORY_QUANTIZATION_CONTRACT_VERSION",
    "QuantizedVariant", "FACTORY_RELEASE_CONTRACT_VERSION", "PublishedExpertPackage",
    "FACTORY_REGRESSION_CONTRACT_VERSION", "RegressionGateResult",
    "FACTORY_LIFECYCLE_CONTRACT_VERSION", "FactoryLifecycleReport",
]
