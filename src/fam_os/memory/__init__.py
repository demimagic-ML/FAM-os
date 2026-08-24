"""Permissioned local memory and retrieval."""

from fam_os.memory.manifest import (
    MEMORY_RECORD_MANIFEST_CONTRACT_VERSION,
    MemoryContentDigest,
    MemoryProvenance,
    MemoryRecordKind,
    MemoryRecordManifest,
    MemoryScope,
    MemorySensitivity,
    MemorySourceKind,
)
from fam_os.memory.lifecycle_contracts import (
    MEMORY_LIFECYCLE_CONTRACT_VERSION,
    MemoryDeletionReason,
    MemoryDeletionReceipt,
    MemoryDeletionRequest,
    MemoryExpiryEvaluation,
    MemoryExpiryState,
)
from fam_os.memory.access import (
    MEMORY_ACCESS_CONTRACT_VERSION,
    MemoryAccessContext,
    scope_allows,
)
from fam_os.memory.ephemeral_store import BoundedEphemeralMemoryStore, StoredMemoryRecord
from fam_os.memory.document_contracts import (
    DOCUMENT_INDEX_CONTRACT_VERSION,
    DocumentIndexApproval,
    DocumentIndexEvidence,
    DocumentRetrievalHit,
    IndexedDocumentChunk,
)
from fam_os.memory.document_index import ApprovedDocumentIndex
from fam_os.memory.document_repository import (
    DocumentIndexRecord,
    DocumentIndexRepository,
    SqliteDocumentIndexRepository,
)
from fam_os.memory.grant_contracts import (
    DOCUMENT_INDEX_GRANT_VERSION,
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    DocumentIndexReceipt,
)
from fam_os.memory.relevance import (
    MEMORY_RELEVANCE_CONTRACT_VERSION,
    MemoryRejection,
    MemoryRelevanceDecision,
    MemoryRelevancePolicy,
    MemoryRetrievalCandidate,
)
from fam_os.memory.management import (
    MAX_MANAGED_DOCUMENT_BYTES,
    MEMORY_MANAGEMENT_CONTRACT_VERSION,
    DocumentCorrectionRequest,
    DocumentDeletionRequest,
    DocumentExpirationRequest,
    DocumentInspection,
    DocumentManagementOperation,
    DocumentManagementReceipt,
    DocumentMemoryManager,
    MemoryDocumentExport,
    MemoryManagementEvidence,
)
from fam_os.memory.encryption import (
    MEMORY_ENCRYPTION_CONTRACT_VERSION,
    AesGcmMemoryCipher,
    MemoryEncryptionEvidence,
    OwnerMemoryKey,
)
from fam_os.memory.quality_evidence import (
    MEMORY_QUALITY_CONTRACT_VERSION,
    MemoryQualityCase,
    MemoryQualityPrivacyReport,
)
from fam_os.memory.phase10_exit import PHASE10_EXIT_CONTRACT_VERSION, Phase10ExitEvidence
from fam_os.memory.session_memory import ProductionSessionMemory, SessionMemoryLimits
from fam_os.memory.document_ingestion import document_chunks

__all__ = [
    "MEMORY_RECORD_MANIFEST_CONTRACT_VERSION",
    "MemoryContentDigest",
    "MemoryProvenance",
    "MemoryRecordKind",
    "MemoryRecordManifest",
    "MemoryScope",
    "MemorySensitivity",
    "MemorySourceKind",
    "MEMORY_LIFECYCLE_CONTRACT_VERSION",
    "MemoryDeletionReason",
    "MemoryDeletionReceipt",
    "MemoryDeletionRequest",
    "MemoryExpiryEvaluation",
    "MemoryExpiryState",
    "MEMORY_ACCESS_CONTRACT_VERSION",
    "MemoryAccessContext",
    "scope_allows",
    "BoundedEphemeralMemoryStore",
    "StoredMemoryRecord",
    "DOCUMENT_INDEX_CONTRACT_VERSION",
    "DocumentIndexApproval",
    "DocumentIndexEvidence",
    "DocumentRetrievalHit",
    "IndexedDocumentChunk",
    "ApprovedDocumentIndex",
    "DocumentIndexRecord",
    "DocumentIndexRepository",
    "SqliteDocumentIndexRepository",
    "DOCUMENT_INDEX_GRANT_VERSION",
    "DocumentIndexGrant",
    "DocumentIndexGrantKind",
    "DocumentIndexReceipt",
    "MEMORY_RELEVANCE_CONTRACT_VERSION",
    "MemoryRejection",
    "MemoryRelevanceDecision",
    "MemoryRelevancePolicy",
    "MemoryRetrievalCandidate",
    "MEMORY_MANAGEMENT_CONTRACT_VERSION",
    "MAX_MANAGED_DOCUMENT_BYTES",
    "DocumentCorrectionRequest",
    "DocumentDeletionRequest",
    "DocumentExpirationRequest",
    "DocumentInspection",
    "DocumentManagementOperation",
    "DocumentManagementReceipt",
    "DocumentMemoryManager",
    "MemoryDocumentExport",
    "MemoryManagementEvidence",
    "MEMORY_ENCRYPTION_CONTRACT_VERSION",
    "AesGcmMemoryCipher",
    "MemoryEncryptionEvidence",
    "OwnerMemoryKey",
    "MEMORY_QUALITY_CONTRACT_VERSION",
    "MemoryQualityCase",
    "MemoryQualityPrivacyReport",
    "PHASE10_EXIT_CONTRACT_VERSION",
    "Phase10ExitEvidence",
    "ProductionSessionMemory",
    "SessionMemoryLimits",
    "document_chunks",
]
