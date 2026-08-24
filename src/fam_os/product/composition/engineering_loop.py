"""Installed product composition for the persistent engineering lifecycle."""

from pathlib import Path
from datetime import datetime, timezone

from fam_os.adapters.sqlite import (
    SQLiteCandidateChangesetStore, SQLiteCandidateEditStore,
    SQLiteCandidateVerificationStore,
    SQLiteEngineeringLoopStore,
    SQLiteEngineeringPreparationStore,
    SQLiteLocalGitDeliveryStore,
    SQLitePublicationConsumptionStore,
    SQLiteEngineeringIncidentStore,
    SQLiteEngineeringReviewStore,
    SQLiteEngineeringDocumentationStore,
    SQLiteRuntimeDiagnosticStore,
    SQLiteDatabaseEngineeringStore,
)
from fam_os.adapters.git import LocalGitAdapter, UnixGitPublicationBroker
from fam_os.product.engineering_loop_api import ProductEngineeringLoopApi
from fam_os.product.storage.engineering_grant_repository import (
    SqliteEngineeringGrantRepository,
)
from fam_os.adapters.bubblewrap.engineering import EngineeringSandboxAdapter
from fam_os.adapters.bubblewrap.diagnostics import (
    BubblewrapRuntimeDiagnosticAdapter,
)
from fam_os.adapters.database import NaturalSQLitePlanBuilder
from fam_os.core.engineering import (
    CandidateVerificationService, GitPublicationService,
    LocalGitDeliveryService, EngineeringIncidentService,
    EngineeringReviewService,
    RuntimeDiagnosticRecipePolicy, RuntimeDiagnosticService,
)
from fam_os.verification.engineering import SignedEngineeringReceiptVerifier


def compose_engineering_loop(
    state_root: Path,
    owner_id: str,
    grants: SqliteEngineeringGrantRepository,
    authorizer,
    recipes=None,
    publication_broker_socket: Path | None = None,
    publication_proposals=None,
    incident_codec=None,
    review_codec=None,
    documentation_codec=None,
    documentation_recipes=None,
    runtime_diagnostic_codec=None,
    release_root: Path | None = None,
    database_engineering=None,
    database_host_id: str | None = None,
    database_codec=None,
    sandbox_apparmor_profile: str | None = None,
) -> ProductEngineeringLoopApi:
    verifications = SQLiteCandidateVerificationStore(
        state_root / "state/engineering-candidate-verifications.sqlite3",
    )
    verifications.recover_pending(datetime.now(timezone.utc))
    verification_service = None
    runtime_diagnostic_service = None
    runtime_diagnostic_store = SQLiteRuntimeDiagnosticStore(
        state_root / "state/engineering-runtime-diagnostics.sqlite3",
        runtime_diagnostic_codec,
    )
    database_store = SQLiteDatabaseEngineeringStore(
        state_root / "state/engineering-database.sqlite3", database_codec,
    )
    if (
        recipes is not None
        and Path("/usr/bin/bwrap").is_file()
        and Path("/usr/bin/systemd-run").is_file()
    ):
        sandbox = EngineeringSandboxAdapter(
            recipes, release_root=release_root,
            apparmor_profile=sandbox_apparmor_profile,
        )
        verification_service = CandidateVerificationService(
            authorizer, recipes, sandbox,
            SignedEngineeringReceiptVerifier(recipes), verifications,
        )
        diagnostic_policy = RuntimeDiagnosticRecipePolicy(recipes)
        runtime_diagnostic_service = RuntimeDiagnosticService(
            authorizer, diagnostic_policy,
            BubblewrapRuntimeDiagnosticAdapter(diagnostic_policy, sandbox),
            runtime_diagnostic_store,
        )
    return ProductEngineeringLoopApi(
        owner_id,
        grants,
        SQLiteEngineeringLoopStore(state_root / "state/engineering-loop.sqlite3"),
        state_root / "engineering/candidates",
        SQLiteEngineeringPreparationStore(
            state_root / "state/engineering-preparation.sqlite3",
        ),
        authorizer,
        SQLiteCandidateEditStore(
            state_root / "state/engineering-candidate-edits.sqlite3",
        ),
        verification_service,
        verifications,
        SQLiteCandidateChangesetStore(
            state_root / "state/engineering-candidate-changesets.sqlite3",
        ),
        recipes,
        LocalGitDeliveryService(
            authorizer, LocalGitAdapter(),
            SQLiteLocalGitDeliveryStore(
                state_root / "state/engineering-local-git-delivery.sqlite3",
            ),
        ),
        None if publication_broker_socket is None else GitPublicationService(
            UnixGitPublicationBroker(publication_broker_socket),
            SQLitePublicationConsumptionStore(
                state_root / "state/engineering-git-publication.sqlite3",
            ),
            publication_proposals,
        ),
        EngineeringIncidentService(SQLiteEngineeringIncidentStore(
            state_root / "state/engineering-incidents.sqlite3",
            incident_codec,
        )),
        EngineeringReviewService(SQLiteEngineeringReviewStore(
            state_root / "state/engineering-reviews.sqlite3",
            review_codec,
        )),
        SQLiteEngineeringDocumentationStore(
            state_root / "state/engineering-documentation.sqlite3",
            documentation_codec,
        ),
        documentation_recipes,
        runtime_diagnostic_service,
        runtime_diagnostic_store,
        (
            None if database_host_id is None
            else NaturalSQLitePlanBuilder(database_host_id)
        ),
        (
            None if database_engineering is None
            else database_engineering.service
        ),
        database_store,
    )
