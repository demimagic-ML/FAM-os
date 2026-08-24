"""Production composition for the owner-scoped Shell, Core, Ollama, and Console."""
from __future__ import annotations

import os
import socket
import threading
import hashlib
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.codex_subscription import CodexSubscriptionSettings
from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.adapters.shell import ShellRequestDispatcher, UnixShellServer, UnixShellServerConfiguration
from fam_os.applications.transport import PeerAuthorizationPolicy
from fam_os.console.http import ConsoleHttpServer
from fam_os.console.conversation_turns import ConsoleConversationTurnApi
from fam_os.core.production.turn_resolution import (
    ConversationTurnResolverSettings,
    ModelConversationTurnResolver,
)
from fam_os.console.service import load_or_create_token
from fam_os.console.tasks import ConsoleTaskApi
from fam_os.core.production.gateway import ProductionTaskGateway
from fam_os.core.production.model_selection import ResourceAwareModelSelector
from fam_os.product.composition.catalog_unit import active_release_id, active_release_root, runtime_catalog
from fam_os.product.composition.integration_recipes import (
    installed_engineering_recipe_catalog, installed_integration_recipe_catalog,
)
from fam_os.product.composition.documentation_recipes import (
    installed_documentation_recipe_catalog,
)
from fam_os.product.composition.review_recipes import (
    installed_engineering_reviewer_catalog,
)
from fam_os.product.composition.console_state import ProductConsoleProvider
from fam_os.product.composition.live_capacity import ProductCapacityObserver
from fam_os.product.composition.mcp_ingress import ProductMcpIngress
from fam_os.product.composition.application_fabric import ApplicationFabric
from fam_os.product.composition.application_services import ApplicationServices
from fam_os.product.application_restart import ApplicationRestartCoordinator
from fam_os.product.composition.factory_training import (
    FactoryTrainingRuntimeSettings,
    compose_factory_training,
)
from fam_os.product.composition.factory_evaluation import (
    FactoryEvaluationRuntimeSettings,
    compose_factory_evaluation,
)
from fam_os.product.composition.factory_release import (
    FactoryReleaseRuntimeSettings,
    FactoryReleaseServices,
    compose_factory_release,
)
from fam_os.product.composition.runtime_unit import ProductRuntimeSettings, ProductRuntimeUnit
from fam_os.product.composition.database_engineering import (
    DatabaseEngineeringUnit,
    compose_database_engineering,
)
from fam_os.product.composition.postgresql_verification import (
    compose_postgresql_verification,
)
from fam_os.product.composition.integration_environment import (
    IntegrationEnvironmentUnit,
    compose_integration_environment,
)
from fam_os.product.composition.integration_network import (
    compose_integration_network_client,
)
from fam_os.product.composition.engineering_inference import (
    compose_engineering_inference,
)
from fam_os.product.composition.engineering_loop import compose_engineering_loop
from fam_os.product.composition.validation_profiles import (
    validation_profile_accelerator_environment,
    validation_profile_resource_limits,
)
from fam_os.product.composition.storage_unit import ProductStorageUnit
from fam_os.product.owner_identity import local_owner_id
from fam_os.product.engineering_authority_api import ProductEngineeringAuthorityApi
from fam_os.product.natural_engineering_api import ProductNaturalEngineeringApi
from fam_os.product.storage.owner_contract_codec import (
    OwnerBoundContractCodec, OwnerBoundJsonCodec,
)
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator,
)
from fam_os.product.natural_engineering_agent import (
    NaturalEngineeringAgentService,
)
from fam_os.product.natural_engineering_documentation import (
    NaturalEngineeringDocumentationCoordinator,
    UnavailableNaturalEngineeringDocumentationCoordinator,
)
from fam_os.product.natural_engineering_review import (
    NaturalEngineeringReviewCoordinator,
)
from fam_os.adapters.sqlite import (
    SQLiteCandidateGenerationStore, SQLiteNaturalEngineeringProposalStore,
    SQLiteGitPublicationProposalStore,
)
from fam_os.core.engineering import (
    CandidateGenerationRecord, CandidateGenerationService,
    DocumentationGenerationService,
    EngineeringIncidentEvidenceReceipt, EngineeringIncidentState,
    EngineeringReviewCheckpoint, EngineeringReviewExecutionService,
    EngineeringReviewResolutionReceipt, EngineeringReviewSelection,
    EngineeringReviewWaiverDecision,
    DocumentationGenerationRequest, DocumentationGovernanceBinding,
    DocumentationRequirementSelection, DocumentationStalenessReport,
    GeneratedDocumentationReceipt, RequirementTraceabilityRecord,
    GitPublicationProposal, GitPublicationReceipt,
    RuntimeDiagnosticRequest, RuntimeDiagnosticReceipt,
    DatabaseChangePlan, DatabaseBackupReceipt, DatabasePostapplyReceipt,
    DatabaseVerificationReceipt,
)
from fam_os.adapters.documentation import DeterministicDocumentationGenerator
from fam_os.adapters.review import DeterministicEngineeringReviewer
from fam_os.adapters.filesystem import BoundedCandidateContextReader
from fam_os.adapters.integration import NaturalIntegrationEnvironmentPlanner
from fam_os.adapters.filesystem.repository_evidence import (
    BoundedFilesystemRepositoryObserver,
)
from fam_os.product.engineering_secret_api import ProductEngineeringSecretApi
from fam_os.product.engineering_secret_lifecycle import (
    EngineeringSecretLifecycleCoordinator,
    UnavailableIntegrationEnvironmentLifecycle,
)
from fam_os.product.natural_engineering_integration import (
    NaturalEngineeringIntegrationCoordinator,
)
from fam_os.product.owned_root import OwnedProductRoot
from fam_os.product.composition.verifier_unit import (
    production_sandbox,
    production_verifier,
    production_verifier_catalog,
)
from fam_os.product.composition.peer_service import ProductPeerService, ProductPeerSettings
from fam_os.product.composition import document_memory
from fam_os.product.peer_capabilities import catalog_capability_source
from fam_os.product.peer_context import ProductPeerContextService
from fam_os.product.peer_management import ProductPeerManagement
from fam_os.product.remote_execution_client import ProductRemoteExecutionClient
from fam_os.product.remote_execution_planner import ProductRemoteExecutionPlanner
from fam_os.product.remote_execution_server import ProductRemoteExecutionServer
from fam_os.product.document_index_service import ProductDocumentIndexService
from fam_os.product.recovery_gateway import RecoveryModeShellGateway
from fam_os.product.verified_outcome_learning import ProductVerifiedOutcomeLearning
from fam_os.product.live_adaptation import ProductLiveAdaptation
from fam_os.product.model_residency import ProductionModelResidency
from fam_os.product.factory_discovery import ProductFactoryDiscovery
from fam_os.product.factory_datasets import ProductFactoryDatasets
from fam_os.product.factory_control import ProductFactoryControl
from fam_os.product.factory_failure_observer import ProductFactoryFailureObserver
from fam_os.product.factory_training_approvals import ProductFactoryTrainingApprovals
from fam_os.product.factory_training import ProductFactoryTraining
from fam_os.product.factory_evaluations import ProductFactoryEvaluationApprovals
from fam_os.product.storage.factory_dataset_blob_store import FactoryDatasetBlobStore
from fam_os.expert_factory import DatasetSplitPolicy
from fam_os.fabric import PersistentDeviceIdentityStore
from fam_os.product.user_isolation import PrivateUserRuntime, UserRuntimeIdentity
from fam_os.product.useful_tasks import UsefulTaskApi, UsefulTaskRepository
from fam_os.product.tool_loop import ToolLoopRepository
from fam_os.product.integration_center import IntegrationCenter
from fam_os.product.automations import AutomationService
from fam_os.product.recipes import RecipeLibrary
from fam_os.adapters.media.local_speech import FasterWhisperRecognizer
from fam_os.memory import ProductionSessionMemory
from fam_os.supervisor import ResourceLimits
from fam_os.scheduler import AcceleratorVisibility, ValidationProfileDocument


@dataclass(frozen=True, slots=True)
class ProductServiceSettings:
    state_root: Path
    runtime_root: Path
    model_ref: str = "qwen3:1.7b"
    ollama_url: str = "http://127.0.0.1:11435"
    console_port: int = 8765
    ready_file: Path | None = None
    manage_ollama: bool = True
    ollama_executable: Path = Path("/usr/local/bin/ollama")
    source_model_root: Path | None = None
    resource_limits: ResourceLimits = ResourceLimits()
    device_display_name: str = "FAM_OS device"
    peer_listen_host: str | None = None
    peer_listen_port: int = 48121
    factory_training_runtime: FactoryTrainingRuntimeSettings | None = None
    factory_evaluation_runtime: FactoryEvaluationRuntimeSettings | None = None
    factory_release_runtime: FactoryReleaseRuntimeSettings | None = None
    validation_profile: ValidationProfileDocument | None = None
    sandbox_apparmor_profile: str | None = None
    integration_network_broker_socket: Path | None = None
    git_publication_broker_socket: Path | None = None
    git_publication_remote_name: str | None = None
    git_publication_credential_ref: str | None = None
    codex_subscription: CodexSubscriptionSettings | None = None

    def __post_init__(self) -> None:
        for socket_name in ("shell.sock", "applications.sock", "mcp-ingress.sock"):
            socket_path = self.runtime_root / socket_name
            if len(os.fsencode(socket_path)) > 107:
                raise ValueError(
                    "FAM_OS runtime socket path exceeds the Linux AF_UNIX bound: "
                    + str(socket_path)
                )
        if (
            self.integration_network_broker_socket is not None
            and not self.integration_network_broker_socket.is_absolute()
        ):
            raise ValueError("integration network broker socket must be absolute")
        if (
            self.git_publication_broker_socket is not None
            and not self.git_publication_broker_socket.is_absolute()
        ):
            raise ValueError("Git publication broker socket must be absolute")
        publication_values = (
            self.git_publication_remote_name,
            self.git_publication_credential_ref,
        )
        if any(value is not None for value in publication_values) and not all(
            isinstance(value, str) and value.strip() for value in publication_values
        ):
            raise ValueError(
                "Git publication remote and credential reference must be configured together"
            )
        if (
            self.codex_subscription is not None
            and self.codex_subscription.work_root
            != self.runtime_root / "codex-inference"
        ):
            raise ValueError(
                "Codex inference work root must stay inside the private runtime root"
            )
        profile = self.validation_profile
        if (
            profile is not None
            and profile.service.accelerator_visibility is AcceleratorVisibility.DENY_ALL
            and not self.manage_ollama
        ):
            raise ValueError(
                "CPU-only validation requires the FAM-managed inference service"
            )

    @property
    def effective_resource_limits(self) -> ResourceLimits:
        if self.validation_profile is None:
            return self.resource_limits
        return validation_profile_resource_limits(self.validation_profile)

class LocalProductService:
    def __init__(
        self, settings: ProductServiceSettings, runtime=None,
        adaptation_health_sampler=None, context_profile_observer=None,
        engineering_runtime=None,
    ) -> None:
        self.settings = settings
        self._runtime = runtime
        self._engineering_runtime = engineering_runtime
        self._engineering_model_ref: str | None = None
        self._adaptation_health_sampler = adaptation_health_sampler
        self._context_profile_observer = context_profile_observer
        self._runtime_unit: ProductRuntimeUnit | None = None
        self._capacity_observer: ProductCapacityObserver | None = None
        self.model_residency: ProductionModelResidency | None = None
        self._storage_unit: ProductStorageUnit | None = None
        self._session_memory: ProductionSessionMemory | None = None
        self.document_indexes: ProductDocumentIndexService | None = None
        self.outcome_learning: ProductVerifiedOutcomeLearning | None = None
        self.live_adaptation: ProductLiveAdaptation | None = None
        self.factory_discovery: ProductFactoryDiscovery | None = None
        self.factory_datasets: ProductFactoryDatasets | None = None
        self.factory_control: ProductFactoryControl | None = None
        self.factory_training_approvals: ProductFactoryTrainingApprovals | None = None
        self.factory_training: ProductFactoryTraining | None = None
        self.factory_evaluation_approvals: ProductFactoryEvaluationApprovals | None = None
        self.factory_evaluator = None
        self.factory_release_services: FactoryReleaseServices | None = None
        self._stop = threading.Event()
        self._shell_thread: threading.Thread | None = None
        self._console_thread: threading.Thread | None = None
        self._application_thread: threading.Thread | None = None
        self.shell_server: UnixShellServer | None = None
        self.console_server: ConsoleHttpServer | None = None
        self.application_fabric: ApplicationFabric | None = None
        self.application_services: ApplicationServices | None = None
        self.action_restart_decisions = ()
        self.mcp_ingress: ProductMcpIngress | None = None
        self.peer_service: ProductPeerService | None = None
        self.peer_context: ProductPeerContextService | None = None
        self._runtime_catalog = None
        self.peer_management: ProductPeerManagement | None = None
        self.remote_execution: ProductRemoteExecutionClient | None = None
        self.database_engineering: DatabaseEngineeringUnit | None = None
        self.engineering_authority_api: ProductEngineeringAuthorityApi | None = None
        self.engineering_secret_api: ProductEngineeringSecretApi | None = None
        self.engineering_loop_api = None
        self.natural_engineering_api = None
        self.integration_environment: IntegrationEnvironmentUnit | None = None
        self.useful_task_api: UsefulTaskApi | None = None
        self.integration_center: IntegrationCenter | None = None
        self.automation_service: AutomationService | None = None
        self.recipe_library: RecipeLibrary | None = None

    def start(self) -> None:
        self._initialize_roots()
        self.application_fabric = ApplicationFabric.compose(
            self.settings.runtime_root / "applications.sock", os.geteuid(),
        )
        gateway = self._gateway()
        if isinstance(gateway, ProductionTaskGateway):
            core = self._storage_unit.core if self._storage_unit is not None else None
            if core is None:
                raise RuntimeError("MCP ingress requires production Core storage")
            capability_source = catalog_capability_source(self._runtime_catalog)
            if self.model_residency is None:
                raise RuntimeError("production model residency was not composed")
            remote_server = ProductRemoteExecutionServer(
                self.model_residency, capability_source, self.model_residency,
            )
            self.peer_service = ProductPeerService(
                ProductPeerSettings(
                    self.settings.state_root, self.settings.device_display_name,
                    self.settings.peer_listen_host, self.settings.peer_listen_port,
                ),
                core.repositories().peer_enrollments,
                os.geteuid(),
                capability_source,
                core.repositories().peer_context,
                remote_server,
            )
            self.peer_service.start()
            repositories = core.repositories()
            self.peer_context = ProductPeerContextService(
                repositories.peer_enrollments, repositories.peer_state,
                repositories.peer_context, self.peer_service,
                local_owner_id(os.geteuid()),
            )
            self.peer_management = ProductPeerManagement(
                repositories.peer_enrollments, repositories.peer_state,
                self.peer_service, local_owner_id(os.geteuid()),
                context=self.peer_context,
            )
            self.remote_execution = ProductRemoteExecutionClient(
                self.peer_context, repositories.peer_enrollments,
                self.peer_service, local_owner_id(os.geteuid()),
            )
            gateway.bind_remote_planner(
                ProductRemoteExecutionPlanner(self.peer_management),
            )
            gateway.bind_remote_executor(self.remote_execution)
            self.mcp_ingress = ProductMcpIngress.from_file(
                self.settings.state_root / "config/mcp-ingress.json",
                self.settings.runtime_root / "mcp-ingress.sock", os.geteuid(),
                gateway, core.repositories(),
            )
            self.mcp_ingress.start()
        memory = self.document_indexes.management if self.document_indexes else None
        self.shell_server = UnixShellServer(
            UnixShellServerConfiguration(self.settings.runtime_root / "shell.sock"),
            PeerAuthorizationPolicy(os.geteuid()),
            ShellRequestDispatcher(
                gateway, memory, adaptation=self.live_adaptation,
                peer=self.peer_management,
                engineering_authority=self.engineering_authority_api,
                integration_environment=(
                    None if self.integration_environment is None
                    else self.integration_environment.api
                ),
                engineering_secrets=self.engineering_secret_api,
                engineering_loop=self.engineering_loop_api,
                natural_engineering=self.natural_engineering_api,
            ),
        )
        token = load_or_create_token(self.settings.runtime_root / "console.token")
        storage = None if self._storage_unit is None else self._storage_unit.result
        if storage is None:
            raise RuntimeError("Console requires secure storage state")
        console_repositories = (
            None
            if self._storage_unit is None or self._storage_unit.core is None
            else self._storage_unit.core.repositories()
        )
        database = storage.database
        if database is not None:
            delegate = None
            if self.natural_engineering_api is not None:
                owner_id = local_owner_id(os.geteuid())
                natural_engineering = self.natural_engineering_api

                def delegate(prompt, root):
                    return natural_engineering.propose(owner_id, prompt, root)
            self.useful_task_api = UsefulTaskApi(
                UsefulTaskRepository(database),
                recognizer=FasterWhisperRecognizer(
                    download_root=self.settings.state_root / "models/whisper",
                ),
                engineering_delegate=delegate,
                tool_loop_repository=ToolLoopRepository(database),
            )
            self.integration_center = IntegrationCenter(
                database,
                state_root=self.settings.state_root,
                mcp_clients=(
                    None if self.application_services is None
                    else self.application_services.mcp_clients
                ),
            )
            self.automation_service = AutomationService(database, self.useful_task_api)
            self.recipe_library = RecipeLibrary(database, self.useful_task_api)
        self.console_server = ConsoleHttpServer(
            ("127.0.0.1", self.settings.console_port),
            ProductConsoleProvider(
                self.settings.state_root, active_release_id(), storage=storage,
                capacity=self._capacity_observer,
                catalog=self._runtime_catalog,
                residency=self.model_residency,
                repositories=console_repositories,
                document_indexes=self.document_indexes,
                session_memory=self._session_memory,
                application_audit=(
                    None if self.application_services is None
                    else self.application_services.audit
                ),
            ),
            token,
            ConsoleTaskApi(gateway, self.application_services),
            self.document_indexes,
            self.live_adaptation,
            self.peer_management,
            self.factory_control,
            engineering_authority_api=self.engineering_authority_api,
            integration_environment_api=(
                None if self.integration_environment is None
                else self.integration_environment.api
            ),
            engineering_secret_api=self.engineering_secret_api,
            engineering_loop_api=self.engineering_loop_api,
            natural_engineering_api=self.natural_engineering_api,
            useful_task_api=self.useful_task_api,
            integration_center=self.integration_center,
            automation_service=self.automation_service,
            recipe_library=self.recipe_library,
            conversation_turn_api=(
                None
                if self._engineering_runtime is None
                or self._engineering_model_ref is None
                else ConsoleConversationTurnApi(
                    "local-owner",
                    self._session_memory,
                    ModelConversationTurnResolver(
                        self._engineering_runtime,
                        ConversationTurnResolverSettings(
                            self._engineering_model_ref,
                        ),
                    ),
                )
            ),
        )
        self.shell_server.open()
        self.application_fabric.open()
        self._shell_thread = threading.Thread(target=self._serve_shell, daemon=True)
        self._console_thread = threading.Thread(
            target=self.console_server.serve_forever, daemon=True,
        )
        self._application_thread = threading.Thread(
            target=self._serve_applications, daemon=True,
        )
        self._shell_thread.start()
        self._console_thread.start()
        self._application_thread.start()
        if self.automation_service is not None:
            self.automation_service.start()
        if self.settings.ready_file is not None:
            self.settings.ready_file.write_text("ready\n")

    def wait(self) -> None:
        self._stop.wait()

    def stop(self) -> None:
        self._stop.set()
        if self.automation_service is not None:
            self.automation_service.stop()
            self.automation_service = None
        if self.useful_task_api is not None:
            self.useful_task_api.close()
            self.useful_task_api = None
        if self.peer_service is not None:
            self.peer_service.stop()
            self.peer_service = None
        self.peer_management = None
        self.peer_context = None
        self.remote_execution = None
        if self.mcp_ingress is not None:
            self.mcp_ingress.close()
            self.mcp_ingress = None
        if self.console_server is not None:
            if self._console_thread is not None:
                self.console_server.shutdown()
            self.console_server.server_close()
            self.console_server = None
        if self.shell_server is not None:
            _wake_shell(self.settings.runtime_root / "shell.sock")
            self.shell_server.close()
        if self.application_services is not None:
            self.application_services.close()
            self.application_services = None
        if self.application_fabric is not None:
            _wake_shell(self.settings.runtime_root / "applications.sock")
            self.application_fabric.close()
        for thread in (
            self._shell_thread, self._console_thread, self._application_thread,
        ):
            if thread is not None:
                thread.join(timeout=5)
        if self.settings.ready_file is not None:
            self.settings.ready_file.unlink(missing_ok=True)
        self.document_indexes = document_memory.close_document_index_service(self.document_indexes)
        if self.live_adaptation is not None:
            self.live_adaptation.stop()
            self.live_adaptation = None
        if self.factory_discovery is not None:
            self.factory_discovery.stop()
            self.factory_discovery = None
        self.factory_datasets = None
        self.factory_control = None
        if self.factory_training is not None:
            self.factory_training.stop()
        self.factory_training = None
        self.factory_training_approvals = None
        self.factory_evaluation_approvals = None
        self.factory_evaluator = None
        self.factory_release_services = None
        if self._runtime_unit is not None:
            self._runtime_unit.stop()
            self._runtime_unit = None
        self._capacity_observer = None
        self.model_residency = None
        if self._storage_unit is not None:
            self._storage_unit.stop()
            self._storage_unit = None
        self.outcome_learning = None
        self._session_memory = None
        self.integration_environment = None
        if self.engineering_loop_api is not None:
            if self.natural_engineering_api is not None:
                self.natural_engineering_api.close()
                self.natural_engineering_api = None
            self.engineering_loop_api.close()
            self.engineering_loop_api = None

    def _initialize_roots(self) -> None:
        PrivateUserRuntime(
            self.settings.state_root,
            UserRuntimeIdentity(local_owner_id(os.geteuid()), os.geteuid()),
        ).initialize()
        OwnedProductRoot(
            self.settings.state_root, "state", os.geteuid(),
        ).initialize()
        self.settings.runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.settings.runtime_root, 0o700)
        OwnedProductRoot(
            self.settings.runtime_root, "runtime", os.geteuid(),
        ).initialize()
        for name in ("experts", "permissions"):
            path = self.settings.state_root / name
            path.mkdir(exist_ok=True, mode=0o700)
            os.chmod(path, 0o700)

    def _serve_shell(self) -> None:
        server = self.shell_server
        if server is None:
            raise RuntimeError("shell server is not initialized")
        while not self._stop.is_set():
            try:
                server.serve_once()
            except (EOFError, OSError, RuntimeError):
                if not self._stop.is_set():
                    self._stop.set()

    def _serve_applications(self) -> None:
        fabric = self.application_fabric
        if fabric is None:
            raise RuntimeError("application fabric is not initialized")
        while not self._stop.is_set():
            try:
                fabric.serve_once()
            except (EOFError, OSError, RuntimeError, ValueError):
                if not self._stop.is_set():
                    self._stop.set()

    def _gateway(self):
        self._storage_unit = ProductStorageUnit(self.settings.state_root, os.geteuid())
        storage = self._storage_unit.start()
        if storage.recovery_required:
            return RecoveryModeShellGateway(storage.reason)
        runtime = self._runtime
        if runtime is None and self.settings.manage_ollama:
            self._runtime_unit = ProductRuntimeUnit(ProductRuntimeSettings(
                self.settings.ollama_executable,
                self.settings.state_root / "models",
                self.settings.source_model_root,
                self.settings.model_ref,
                self.settings.ollama_url,
                self.settings.effective_resource_limits,
                (
                    ()
                    if self.settings.validation_profile is None
                    else validation_profile_accelerator_environment(
                        self.settings.validation_profile,
                    )
                ),
            ))
            runtime = self._runtime_unit.start()
        if runtime is None:
            runtime = OllamaRuntime(OllamaSettings(self.settings.ollama_url, 180))
        self._runtime = runtime
        engineering_inference = compose_engineering_inference(
            runtime, self.settings.model_ref, self.settings.codex_subscription,
            self._engineering_runtime,
        )
        self._engineering_runtime = engineering_inference.runtime
        self._engineering_model_ref = engineering_inference.model_ref
        core = self._storage_unit.core
        if core is None or storage.cipher is None or storage.database is None:
            raise RuntimeError("production Core storage was not composed")
        if self._storage_unit.engineering_authorizer is None:
            raise RuntimeError("engineering authority was not composed")
        if (
            self._storage_unit.engineering_authentication is None
            or self._storage_unit.engineering_grants is None
        ):
            raise RuntimeError("engineering owner authority facade was not composed")
        self.engineering_authority_api = ProductEngineeringAuthorityApi(
            local_owner_id(os.geteuid()),
            self._storage_unit.engineering_grants,
            self._storage_unit.engineering_authentication,
            self._storage_unit.engineering_authorizer,
        )
        engineering_recipes = installed_engineering_recipe_catalog(
            active_release_root(),
        )
        documentation_recipes = installed_documentation_recipe_catalog(
            active_release_root(),
        )
        reviewer_recipes = installed_engineering_reviewer_catalog(
            active_release_root(),
        )
        self.database_engineering = compose_database_engineering(
            local_owner_id(os.geteuid()), storage.cipher,
            self._storage_unit.engineering_authorizer,
        )
        self.engineering_loop_api = compose_engineering_loop(
            self.settings.state_root,
            local_owner_id(os.geteuid()),
            self._storage_unit.engineering_grants,
            self._storage_unit.engineering_authorizer,
            engineering_recipes,
            self.settings.git_publication_broker_socket,
            (
                None
                if self.settings.git_publication_broker_socket is None
                else SQLiteGitPublicationProposalStore(
                    self.settings.state_root
                    / "state/engineering-git-publication-proposals.sqlite3",
                    OwnerBoundContractCodec(
                        storage.cipher, local_owner_id(os.geteuid()),
                        "engineering-git-publication-proposal",
                        GitPublicationProposal,
                    ),
                    OwnerBoundContractCodec(
                        storage.cipher, local_owner_id(os.geteuid()),
                        "engineering-git-publication-receipt",
                        GitPublicationReceipt,
                    ),
                )
            ),
            OwnerBoundContractCodec(
                storage.cipher, local_owner_id(os.geteuid()),
                "engineering-incident",
                (EngineeringIncidentState, EngineeringIncidentEvidenceReceipt),
            ),
            OwnerBoundContractCodec(
                storage.cipher, local_owner_id(os.geteuid()),
                "engineering-review",
                (
                    EngineeringReviewCheckpoint,
                    EngineeringReviewResolutionReceipt,
                    EngineeringReviewSelection,
                    EngineeringReviewWaiverDecision,
                ),
            ),
            OwnerBoundContractCodec(
                storage.cipher, local_owner_id(os.geteuid()),
                "engineering-documentation",
                (
                    DocumentationGenerationRequest,
                    DocumentationGovernanceBinding,
                    DocumentationRequirementSelection,
                    GeneratedDocumentationReceipt,
                    DocumentationStalenessReport,
                    RequirementTraceabilityRecord,
                ),
            ),
            documentation_recipes,
            OwnerBoundContractCodec(
                storage.cipher, local_owner_id(os.geteuid()),
                "engineering-runtime-diagnostic",
                (RuntimeDiagnosticRequest, RuntimeDiagnosticReceipt),
            ),
            active_release_root(),
            self.database_engineering,
            f"local-host-{os.uname().nodename}",
            OwnerBoundContractCodec(
                storage.cipher, local_owner_id(os.geteuid()),
                "engineering-database",
                (
                    DatabaseChangePlan, DatabaseBackupReceipt,
                    DatabaseVerificationReceipt, DatabasePostapplyReceipt,
                ),
            ),
            self.settings.sandbox_apparmor_profile,
        )
        secret_lifecycle = EngineeringSecretLifecycleCoordinator()
        integration_network = compose_integration_network_client(
            self.settings.integration_network_broker_socket,
            identity_root=self.settings.state_root / "fabric/identity",
            display_name=self.settings.device_display_name,
            owner_uid=os.geteuid(),
        )
        self.integration_environment = compose_integration_environment(
            self._storage_unit.engineering_authorizer,
            owner_id=local_owner_id(os.geteuid()),
            repository=self._storage_unit.integration_environments,
            process_recipes=installed_integration_recipe_catalog(
                active_release_root()
            ),
            secrets=self._storage_unit.engineering_secrets,
            lifecycle=secret_lifecycle,
            network_broker=(
                None if integration_network is None else
                integration_network.broker
            ),
            network_authority=(
                None if integration_network is None else
                integration_network.authority
            ),
        )
        postgresql_verification = compose_postgresql_verification(
            local_owner_id(os.geteuid()), storage.cipher,
            self._storage_unit.engineering_authorizer,
        )
        natural_integration = (
            None if self.integration_environment is None else
            NaturalEngineeringIntegrationCoordinator(
                self.engineering_loop_api,
                self.integration_environment.api,
                NaturalIntegrationEnvironmentPlanner(
                    f"local-host-{os.uname().nodename}",
                ),
                resource_grant_resolver=(
                    self._storage_unit.engineering_grants.usable
                ),
                postgresql_planner=postgresql_verification.planner,
                postgresql_verifier=postgresql_verification.service,
            )
        )
        self.natural_engineering_api = ProductNaturalEngineeringApi(
            local_owner_id(os.geteuid()),
            SQLiteNaturalEngineeringProposalStore(
                self.settings.state_root / "state/natural-engineering.sqlite3",
                OwnerBoundJsonCodec(
                    storage.cipher, local_owner_id(os.geteuid()),
                    "natural-engineering-proposal",
                ),
            ),
            self._storage_unit.engineering_authentication,
            self._storage_unit.engineering_authorizer,
            self.engineering_loop_api,
            BoundedFilesystemRepositoryObserver(),
            executor=NaturalEngineeringExecutionCoordinator(
                self.engineering_loop_api,
                BoundedCandidateContextReader(),
                CandidateGenerationService(
                    engineering_inference.runtime, engineering_inference.model_ref,
                    SQLiteCandidateGenerationStore(
                        self.settings.state_root
                        / "state/engineering-candidate-generation.sqlite3",
                        OwnerBoundContractCodec(
                            storage.cipher, local_owner_id(os.geteuid()),
                            "engineering-candidate-generation",
                            CandidateGenerationRecord,
                        ),
                    ),
                ),
                documentation=(
                    UnavailableNaturalEngineeringDocumentationCoordinator()
                    if documentation_recipes is None else
                    NaturalEngineeringDocumentationCoordinator(
                        self.engineering_loop_api,
                        DocumentationGenerationService(
                            documentation_recipes,
                            DeterministicDocumentationGenerator(),
                        ),
                    )
                ),
                reviewer=(
                    None if reviewer_recipes is None else
                    NaturalEngineeringReviewCoordinator(
                        self.engineering_loop_api,
                        EngineeringReviewExecutionService(
                            reviewer_recipes,
                            DeterministicEngineeringReviewer(),
                        ),
                    )
                ),
                integration=natural_integration,
                agent=NaturalEngineeringAgentService(
                    engineering_inference.runtime,
                    engineering_inference.model_ref,
                    storage.database,
                    self.engineering_loop_api,
                    application_provider=lambda: (
                        None if self.application_services is None
                        else self.application_services.provider
                    ),
                ),
            ),
            publication_remote_name=self.settings.git_publication_remote_name,
            publication_credential_ref=(
                self.settings.git_publication_credential_ref
            ),
            grant_reader=self._storage_unit.engineering_grants,
        )
        self.engineering_secret_api = ProductEngineeringSecretApi(
            local_owner_id(os.geteuid()),
            self._storage_unit.engineering_secrets,
            self._storage_unit.engineering_authentication,
            lifecycle=secret_lifecycle,
            environments=(
                UnavailableIntegrationEnvironmentLifecycle(
                    local_owner_id(os.geteuid()),
                    self._storage_unit.integration_environments,
                )
                if self.integration_environment is None
                else self.integration_environment.api
            ),
        )
        repositories = core.repositories()
        sandbox = production_sandbox(self.settings.sandbox_apparmor_profile)
        if self.application_fabric is None:
            raise RuntimeError("application fabric was not composed")
        self.application_services = ApplicationServices.compose(
            self.application_fabric, repositories, self.settings.state_root,
        )
        self.action_restart_decisions = ApplicationRestartCoordinator(
            repositories, self.application_services,
        ).reconcile()
        catalog = runtime_catalog(
            self.settings.model_ref, self.settings.source_model_root,
        )
        release_provenances = catalog.provenances()
        release_expert_ids = {item.expert_id for item in release_provenances}
        for provenance in release_provenances:
            model = catalog.entry_for_provenance(provenance)
            repositories.expert_enablement.synchronize(provenance, model)
        if release_provenances:
            catalog = catalog.enabled(repositories.expert_enablement.enabled_expert_ids())
        factory_lineages = {
            (
                item.expert_id,
                f"{item.package_id}@{item.package_version}",
                item.runtime_model_ref,
            )
            for item in repositories.factory_releases.lineages()
        }
        for provenance, model in repositories.expert_enablement.enabled_models():
            if provenance.expert_id in release_expert_ids:
                continue
            if (
                provenance.expert_id,
                provenance.package_ref,
                provenance.model_ref,
            ) not in factory_lineages:
                continue
            catalog.install_runtime_model(model, provenance)
        verifier_catalog = production_verifier_catalog()
        catalog.require_available_verifiers(verifier_catalog.verifier_ids())
        self._runtime_catalog = catalog
        self._capacity_observer = ProductCapacityObserver(
            managed_resource_snapshot=(
                None if self._runtime_unit is None
                else self._runtime_unit.resource_snapshot
            ),
            validation_profile=self.settings.validation_profile,
        )
        self.model_residency = ProductionModelResidency(
            self.settings.state_root / "scheduler/model-residency.json",
            catalog,
            runtime,
            self._capacity_observer.observe,
            self._runtime_unit,
            self.settings.ollama_url,
            eviction_allowed=self._runtime_unit is not None,
            profile_observer=self._context_profile_observer,
        )
        self.live_adaptation = ProductLiveAdaptation(
            repositories, catalog, self.model_residency, self.model_residency,
            self._capacity_observer.observe,
            health_sampler=self._adaptation_health_sampler,
        )
        self.live_adaptation.start()
        self.factory_discovery = ProductFactoryDiscovery(repositories)
        self.factory_discovery.start()
        dataset_blob_store = FactoryDatasetBlobStore(
            self.settings.state_root / "factory/datasets", storage.cipher,
            local_owner_id(os.geteuid()), os.geteuid(),
        )
        self.factory_datasets = ProductFactoryDatasets(
            repositories,
            DatasetSplitPolicy(
                "factory-split-v1",
                hashlib.sha256(b"fam-os-phase22-split-policy-v1").hexdigest(),
            ),
            dataset_blob_store,
        )
        self.factory_training_approvals = ProductFactoryTrainingApprovals(repositories)
        self.factory_evaluation_approvals = ProductFactoryEvaluationApprovals(repositories)
        if self.settings.factory_training_runtime is not None:
            self.factory_training = compose_factory_training(
                self.settings.factory_training_runtime, repositories,
                dataset_blob_store, os.geteuid(),
            )
        credentials = None
        if (
            self.settings.factory_evaluation_runtime is not None
            or self.settings.factory_release_runtime is not None
        ):
            credentials = PersistentDeviceIdentityStore(
                self.settings.state_root / "fabric/identity", os.geteuid(),
            ).resolve(self.settings.device_display_name)
        if self.settings.factory_evaluation_runtime is not None:
            if credentials is None:
                raise RuntimeError("factory identity was not composed")
            self.factory_evaluator = compose_factory_evaluation(
                self.settings.factory_evaluation_runtime, repositories,
                dataset_blob_store, credentials, os.geteuid(),
            )
        if self.settings.factory_release_runtime is not None:
            if credentials is None:
                raise RuntimeError("factory identity was not composed")
            self.factory_release_services = compose_factory_release(
                settings=self.settings.factory_release_runtime,
                repositories=repositories, credentials=credentials,
                runtime=self.model_residency,
                catalog=catalog, owner_uid=os.geteuid(), sandbox=sandbox,
            )
        self.factory_control = ProductFactoryControl(
            self.factory_discovery, self.factory_datasets, repositories, catalog,
            self.model_residency, self.model_residency,
            self.factory_training_approvals,
            self.factory_training, self.factory_evaluation_approvals,
            self.factory_evaluator, self.factory_release_services,
        )
        self.outcome_learning = ProductVerifiedOutcomeLearning(
            repositories, self.live_adaptation,
        )
        self.document_indexes = document_memory.compose_document_index_service(
            repositories, self.model_residency, self.model_residency,
            catalog, os.geteuid(),
        )
        grounding = document_memory.compose_grounded_retrieval(
            repositories, self.model_residency, self.model_residency,
            os.geteuid(),
        )
        self._session_memory = ProductionSessionMemory()
        return ProductionTaskGateway(
            runtime, repositories, ResourceAwareModelSelector(catalog, self.live_adaptation),
            self.model_residency.capacity_for_selection,
            core.budget_ledger, self._runtime_unit,
            verifier=production_verifier(repositories, sandbox, verifier_catalog),
            applications=self.application_services,
            memory=self._session_memory,
            grounding=grounding,
            outcomes=self.outcome_learning,
            adaptation=self.live_adaptation,
            failure_observer=ProductFactoryFailureObserver(
                self.factory_discovery,
                None if self.factory_release_services is None
                else self.factory_release_services.lifecycle,
            ),
            residency=self.model_residency,
        )


def main(argv=None) -> int:
    from fam_os.product.service_cli import run
    return run(argv)


def _wake_shell(path: Path) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.connect(str(path))
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
