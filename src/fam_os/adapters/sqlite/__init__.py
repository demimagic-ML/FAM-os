"""SQLite persistence adapters."""

from fam_os.adapters.sqlite.engineering_loop import SQLiteEngineeringLoopStore
from fam_os.adapters.sqlite.publication_consumption import SQLitePublicationConsumptionStore
from fam_os.adapters.sqlite.engineering_review import SQLiteEngineeringReviewStore
from fam_os.adapters.sqlite.engineering_runtime_diagnostic import (
    SQLiteRuntimeDiagnosticStore,
)
from fam_os.adapters.sqlite.engineering_database import (
    SQLiteDatabaseEngineeringStore,
)
from fam_os.adapters.sqlite.engineering_incident import SQLiteEngineeringIncidentStore
from fam_os.adapters.sqlite.engineering_documentation import SQLiteEngineeringDocumentationStore
from fam_os.adapters.sqlite.engineering_preparation import SQLiteEngineeringPreparationStore
from fam_os.adapters.sqlite.engineering_candidate_edit import SQLiteCandidateEditStore
from fam_os.adapters.sqlite.engineering_candidate_verification import SQLiteCandidateVerificationStore
from fam_os.adapters.sqlite.engineering_candidate_changeset import SQLiteCandidateChangesetStore
from fam_os.adapters.sqlite.natural_engineering import SQLiteNaturalEngineeringProposalStore
from fam_os.adapters.sqlite.candidate_generation import SQLiteCandidateGenerationStore
from fam_os.adapters.sqlite.local_git_delivery import SQLiteLocalGitDeliveryStore
from fam_os.adapters.sqlite.git_publication_proposal import (
    SQLiteGitPublicationProposalStore,
)

__all__ = [
    "SQLiteEngineeringDocumentationStore", "SQLiteEngineeringIncidentStore",
    "SQLiteEngineeringLoopStore",
    "SQLiteEngineeringReviewStore",
    "SQLiteRuntimeDiagnosticStore",
    "SQLiteDatabaseEngineeringStore",
    "SQLiteEngineeringPreparationStore",
    "SQLiteCandidateEditStore",
    "SQLiteCandidateVerificationStore",
    "SQLiteCandidateChangesetStore",
    "SQLiteCandidateGenerationStore",
    "SQLiteNaturalEngineeringProposalStore",
    "SQLiteLocalGitDeliveryStore",
    "SQLitePublicationConsumptionStore",
    "SQLiteGitPublicationProposalStore",
]
