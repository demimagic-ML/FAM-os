"""Ports separating training orchestration from the isolated backend."""

from typing import Protocol

from fam_os.expert_factory.training_backend import (
    AdapterTrainingJob,
    TrainingBackendEnvironment,
    TrainingTerminalReceipt,
)


class TrainingBackend(Protocol):
    def probe(self) -> TrainingBackendEnvironment: ...

    def run(self, job: AdapterTrainingJob) -> TrainingTerminalReceipt: ...
