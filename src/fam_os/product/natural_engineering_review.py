"""Natural-loop orchestration for policy-selected signed independent review."""

from fam_os.core.engineering import EngineeringReviewSelectionPolicy


class NaturalEngineeringReviewCoordinator:
    def __init__(self, loop, execution_service, policy=None) -> None:
        self._loop = loop
        self._execution = execution_service
        self._policy = policy or EngineeringReviewSelectionPolicy()

    def review(self, owner_id, definition, changeset, *, producer_id):
        selection = self._policy.select(definition, changeset)
        self._loop.record_review_selection(owner_id, selection)
        checkpoint = self._execution.review(
            selection, changeset, producer_id=producer_id,
        )
        self._loop.record_trusted_review(owner_id, checkpoint)
        return selection, checkpoint
