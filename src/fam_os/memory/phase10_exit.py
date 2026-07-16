"""Memory-fabric exit-gate evidence."""

from dataclasses import dataclass

PHASE10_EXIT_CONTRACT_VERSION = "fam.memory.phase10-exit/v1alpha1"


@dataclass(frozen=True, slots=True)
class Phase10ExitEvidence:
    evidence_id: str
    persistent_items_inspectable: bool
    persistent_items_deletable: bool
    deletion_left_zero_chunks: bool
    cross_scope_hits: int
    encrypted_plaintext_leaks: int
    retrieval_top1_accuracy: float
    passed: bool
    contract_version: str = PHASE10_EXIT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        expected = all((self.persistent_items_inspectable, self.persistent_items_deletable,
                        self.deletion_left_zero_chunks))
        expected = expected and self.cross_scope_hits == 0 and self.encrypted_plaintext_leaks == 0
        expected = expected and self.retrieval_top1_accuracy >= .8
        if self.passed != expected:
            raise ValueError("Phase 10 exit must derive from memory evidence")
