"""Production composition for opt-in persistent document memory."""

from __future__ import annotations

from datetime import UTC, datetime

from fam_os.memory import ApprovedDocumentIndex
from fam_os.memory.document_ingestion import SecureDocumentIngestor
from fam_os.product.document_index_service import ProductDocumentIndexService
from fam_os.product.document_management_service import ProductDocumentManagementService
from fam_os.product.grounded_retrieval import ProductGroundedRetrieval


def compose_document_index_service(
    repositories, runtime, runtime_unit, catalog, owner_uid: int,
) -> ProductDocumentIndexService | None:
    repository = repositories.document_indexes
    repository.purge_expired(datetime.now(UTC))
    model = next((entry for entry in catalog.entries() if entry.tier == "embedding"), None)
    if model is None:
        return None
    index = ApprovedDocumentIndex(repository, runtime)
    ingestor = SecureDocumentIngestor(
        repository, index, owner_uid, model_loader=runtime_unit,
    )
    management = ProductDocumentManagementService(
        repository, index, str(owner_uid), runtime_unit,
    )
    service = ProductDocumentIndexService(
        repository, ingestor, str(owner_uid), model.model_ref, model.manifest_sha256,
        management=management,
    )
    service.start()
    return service


def close_document_index_service(
    service: ProductDocumentIndexService | None,
) -> ProductDocumentIndexService | None:
    if service is not None:
        service.close()
    return None


def compose_grounded_retrieval(
    repositories, runtime, runtime_unit, owner_uid: int,
) -> ProductGroundedRetrieval:
    return ProductGroundedRetrieval(
        ApprovedDocumentIndex(repositories.document_indexes, runtime),
        repositories.document_indexes,
        str(owner_uid),
        model_loader=runtime_unit,
    )
