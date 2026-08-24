"""Canonical content identity for bounded repository evidence."""

import hashlib

from fam_os.core.engineering.repository.contracts import RepositoryEvidenceBundle


def repository_evidence_digest(evidence: RepositoryEvidenceBundle) -> str:
    values = [evidence.workspace_revision]
    values.extend(f"{item.path}:{item.content_sha256}" for item in evidence.files)
    values.extend(item.record_id for item in evidence.context_records)
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()
