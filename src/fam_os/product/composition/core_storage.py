"""Production Core repository composition with no volatile fallbacks."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.core.lifecycle.global_budget import GlobalAttemptBudget
from fam_os.product.storage.admission_repositories import (
    SqliteRequestAuthorityRegistry,
    SqliteRequestReplayRegistry,
)
from fam_os.product.storage.budget_repository import SqliteGlobalAttemptBudgetLedger
from fam_os.product.storage.application_permission_repository import (
    SqliteApplicationPermissionRepository,
)
from fam_os.product.storage.action_repository import SqliteActionStateRepository
from fam_os.product.storage.application_execution_repository import (
    SqliteApplicationExecutionRepository,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.database import ProductionDatabase
from fam_os.product.storage.final_evidence_repository import SqliteFinalEvidenceRegistry
from fam_os.product.storage.expert_enablement_repository import SqliteExpertEnablementRepository
from fam_os.product.storage.inference_repository import SqliteInferenceExecutionRepository
from fam_os.product.storage.lifecycle_repositories import (
    SqliteAttemptPolicyRegistry,
    SqliteAttemptReplayRegistry,
    SqliteDeadlinePolicyRegistry,
    SqliteReplayRegistry,
)
from fam_os.product.storage.plan_repository import SqlitePlanStateRepository
from fam_os.product.storage.request_repository import SqliteTaskRequestRepository
from fam_os.product.storage.verification_repository import SqliteVerificationRepository
from fam_os.product.storage.document_index_repository import (
    SqliteProductDocumentIndexRepository,
)
from fam_os.product.storage.terminal_outcome_repository import (
    SqliteTerminalOutcomeRepository,
)
from fam_os.product.storage.live_adaptation_repository import (
    SqliteLiveAdaptationRepository,
)
from fam_os.product.storage.adaptation_control_repository import (
    SqliteAdaptationControlRepository,
)
from fam_os.product.storage.peer_enrollment_repository import (
    SqlitePeerEnrollmentRepository,
)
from fam_os.product.storage.peer_state_repository import SqlitePeerStateRepository
from fam_os.product.storage.peer_context_repository import SqlitePeerContextRepository
from fam_os.product.storage.factory_discovery_repository import (
    SqliteFactoryDiscoveryRepository,
)
from fam_os.product.storage.capture_grant_repository import (
    SqliteCaptureGrantRepository,
)
from fam_os.product.storage.dataset_staging_repository import (
    SqliteDatasetStagingRepository,
)
from fam_os.product.storage.training_approval_repository import (
    SqliteTrainingApprovalRepository,
)
from fam_os.product.storage.sealed_dataset_repository import (
    SqliteSealedDatasetRepository,
)
from fam_os.product.storage.training_job_repository import SqliteTrainingJobRepository
from fam_os.product.storage.training_admission_repository import (
    SqliteTrainingAdmissionRepository,
)
from fam_os.product.storage.factory_evaluation_repository import (
    SqliteFactoryEvaluationRepository,
)
from fam_os.product.storage.factory_conversion_repository import (
    SqliteFactoryConversionRepository,
)
from fam_os.product.storage.factory_release_repository import (
    SqliteFactoryReleaseRepository,
)
from fam_os.product.storage.factory_lifecycle_repository import (
    SqliteFactoryLifecycleRepository,
)
from fam_os.product.storage.engineering_grant_repository import (
    SqliteEngineeringGrantRepository,
)
from fam_os.product.storage.integration_environment_repository import (
    SqliteIntegrationEnvironmentRepository,
)
from fam_os.product.storage.engineering_secret_repository import (
    SqliteEngineeringSecretRepository,
)


@dataclass(frozen=True, slots=True)
class CoreRepositorySet:
    requests: SqliteTaskRequestRepository
    request_replay: SqliteRequestReplayRegistry
    authorities: SqliteRequestAuthorityRegistry
    plans: SqlitePlanStateRepository
    confirmation_replay: SqliteReplayRegistry
    attempt_policies: SqliteAttemptPolicyRegistry
    attempt_replay: SqliteAttemptReplayRegistry
    control_replay: SqliteReplayRegistry
    deadline_policies: SqliteDeadlinePolicyRegistry
    action_execution_replay: SqliteReplayRegistry
    final_evidence: SqliteFinalEvidenceRegistry
    inference_executions: SqliteInferenceExecutionRepository
    expert_enablement: SqliteExpertEnablementRepository
    application_permissions: SqliteApplicationPermissionRepository
    actions: SqliteActionStateRepository
    application_executions: SqliteApplicationExecutionRepository
    verifications: SqliteVerificationRepository
    document_indexes: SqliteProductDocumentIndexRepository
    terminal_outcomes: SqliteTerminalOutcomeRepository
    live_adaptation: SqliteLiveAdaptationRepository
    adaptation_controls: SqliteAdaptationControlRepository
    peer_enrollments: SqlitePeerEnrollmentRepository
    peer_state: SqlitePeerStateRepository
    peer_context: SqlitePeerContextRepository
    factory_discovery: SqliteFactoryDiscoveryRepository
    capture_grants: SqliteCaptureGrantRepository
    dataset_staging: SqliteDatasetStagingRepository
    sealed_datasets: SqliteSealedDatasetRepository
    training_approvals: SqliteTrainingApprovalRepository
    training_jobs: SqliteTrainingJobRepository
    training_admissions: SqliteTrainingAdmissionRepository
    factory_evaluations: SqliteFactoryEvaluationRepository
    factory_conversions: SqliteFactoryConversionRepository
    factory_releases: SqliteFactoryReleaseRepository
    factory_lifecycle: SqliteFactoryLifecycleRepository
    engineering_grants: SqliteEngineeringGrantRepository
    integration_environments: SqliteIntegrationEnvironmentRepository
    engineering_secrets: SqliteEngineeringSecretRepository


class CoreStorageComposition:
    def __init__(
        self,
        database: ProductionDatabase,
        cipher: ProductPayloadCipher,
        owner_id: str,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("Core storage owner must not be empty")
        self._database = database
        self._cipher = cipher
        self._owner_id = owner_id

    def repositories(self) -> CoreRepositorySet:
        database, cipher, owner = self._database, self._cipher, self._owner_id
        return CoreRepositorySet(
            SqliteTaskRequestRepository(database, cipher, owner),
            SqliteRequestReplayRegistry(database),
            SqliteRequestAuthorityRegistry(database, cipher, owner),
            SqlitePlanStateRepository(database, cipher, owner),
            SqliteReplayRegistry(database, "confirmation"),
            SqliteAttemptPolicyRegistry(database, cipher, owner),
            SqliteAttemptReplayRegistry(database),
            SqliteReplayRegistry(database, "control"),
            SqliteDeadlinePolicyRegistry(database, cipher, owner),
            SqliteReplayRegistry(database, "action_execution"),
            SqliteFinalEvidenceRegistry(database, cipher, owner),
            SqliteInferenceExecutionRepository(database, cipher, owner),
            SqliteExpertEnablementRepository(database, cipher, owner),
            SqliteApplicationPermissionRepository(database, cipher, owner),
            SqliteActionStateRepository(database, cipher, owner),
            SqliteApplicationExecutionRepository(database, cipher, owner),
            SqliteVerificationRepository(database, cipher, owner),
            SqliteProductDocumentIndexRepository(database, cipher, owner),
            SqliteTerminalOutcomeRepository(database, cipher, owner),
            SqliteLiveAdaptationRepository(database, cipher, owner),
            SqliteAdaptationControlRepository(database, cipher, owner),
            SqlitePeerEnrollmentRepository(database, cipher, owner),
            SqlitePeerStateRepository(database, cipher, owner),
            SqlitePeerContextRepository(database, cipher, owner),
            SqliteFactoryDiscoveryRepository(database, cipher, owner),
            SqliteCaptureGrantRepository(database, cipher, owner),
            SqliteDatasetStagingRepository(database, cipher, owner),
            SqliteSealedDatasetRepository(database, cipher, owner),
            SqliteTrainingApprovalRepository(database, cipher, owner),
            SqliteTrainingJobRepository(database, cipher, owner),
            SqliteTrainingAdmissionRepository(database, cipher, owner),
            SqliteFactoryEvaluationRepository(database, cipher, owner),
            SqliteFactoryConversionRepository(database, cipher, owner),
            SqliteFactoryReleaseRepository(database, cipher, owner),
            SqliteFactoryLifecycleRepository(database, cipher, owner),
            SqliteEngineeringGrantRepository(database, cipher, owner),
            SqliteIntegrationEnvironmentRepository(database, cipher, owner),
            SqliteEngineeringSecretRepository(database, cipher, owner),
        )

    def budget_ledger(self, budget: GlobalAttemptBudget) -> SqliteGlobalAttemptBudgetLedger:
        return SqliteGlobalAttemptBudgetLedger(
            self._database, self._cipher, self._owner_id, budget,
        )
