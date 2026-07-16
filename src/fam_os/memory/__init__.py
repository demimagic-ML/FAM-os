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
from fam_os.memory.document_repository import SqliteDocumentIndexRepository
from fam_os.memory.relevance import (
    MEMORY_RELEVANCE_CONTRACT_VERSION,
    MemoryRejection,
    MemoryRelevanceDecision,
    MemoryRelevancePolicy,
    MemoryRetrievalCandidate,
)
from fam_os.memory.management import (
    MEMORY_MANAGEMENT_CONTRACT_VERSION,
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
    "SqliteDocumentIndexRepository",
    "MEMORY_RELEVANCE_CONTRACT_VERSION",
    "MemoryRejection",
    "MemoryRelevanceDecision",
    "MemoryRelevancePolicy",
    "MemoryRetrievalCandidate",
    "MEMORY_MANAGEMENT_CONTRACT_VERSION",
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
]
