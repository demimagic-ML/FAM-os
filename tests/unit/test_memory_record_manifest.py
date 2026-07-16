import unittest
from datetime import datetime, timedelta, timezone

from fam_os.memory import (
    MEMORY_RECORD_MANIFEST_CONTRACT_VERSION,
    MemoryContentDigest,
    MemoryProvenance,
    MemoryRecordKind,
    MemoryRecordManifest,
    MemoryScope,
    MemorySensitivity,
    MemorySourceKind,
)


CREATED_AT = datetime(2026, 7, 16, 13, 0, tzinfo=timezone.utc)


def _provenance(**overrides: object) -> MemoryProvenance:
    values = {
        "source_kind": MemorySourceKind.APPLICATION,
        "source_id": "application.code-editor",
        "created_by": "connector.code-editor.reference",
        "captured_at": CREATED_AT,
    }
    values.update(overrides)
    return MemoryProvenance(**values)


def _record(**overrides: object) -> MemoryRecordManifest:
    values = {
        "record_id": "memory.record.001",
        "kind": MemoryRecordKind.SESSION,
        "created_at": CREATED_AT,
        "content_schema_id": "schema.memory.editor-context",
        "content_media_type": "application/json",
        "content_size_bytes": 512,
        "content_digest": MemoryContentDigest("sha256", "c" * 64),
        "scope": MemoryScope(
            owner_id="user.local.001",
            purpose_ids=("purpose.current-task",),
            application_ids=("application.code-editor",),
            workspace_ids=("workspace.project-alpha",),
            session_id="session.001",
        ),
        "provenance": _provenance(),
        "sensitivity": MemorySensitivity.PRIVATE,
        "retention_policy_id": "retention.session-only",
        "expires_at": CREATED_AT + timedelta(hours=4),
    }
    values.update(overrides)
    return MemoryRecordManifest(**values)


class MemoryRecordManifestTests(unittest.TestCase):
    def test_records_scope_provenance_retention_and_content_integrity(self) -> None:
        record = _record()
        self.assertEqual(record.contract_version, MEMORY_RECORD_MANIFEST_CONTRACT_VERSION)
        self.assertEqual(record.scope.owner_id, "user.local.001")
        self.assertEqual(record.provenance.source_kind, MemorySourceKind.APPLICATION)
        self.assertEqual(record.content_digest.algorithm, "sha256")

    def test_session_memory_requires_session_scope(self) -> None:
        scope = MemoryScope("user.local.001", ("purpose.current-task",))
        with self.assertRaisesRegex(ValueError, "require session scope"):
            _record(scope=scope)

    def test_scope_requires_explicit_purpose(self) -> None:
        with self.assertRaisesRegex(ValueError, "purpose_ids"):
            MemoryScope("user.local.001", ())

    def test_expiry_must_follow_creation(self) -> None:
        with self.assertRaisesRegex(ValueError, "follow created_at"):
            _record(expires_at=CREATED_AT)

    def test_derived_memory_requires_parent_records(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires parent"):
            _provenance(source_kind=MemorySourceKind.DERIVED)

    def test_record_cannot_derive_from_itself(self) -> None:
        provenance = _provenance(
            source_kind=MemorySourceKind.DERIVED,
            parent_record_ids=("memory.record.001",),
        )
        with self.assertRaisesRegex(ValueError, "derive from itself"):
            _record(provenance=provenance)

    def test_requires_supported_contract_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "contract_version"):
            _record(contract_version="fam.memory.record/v2")


if __name__ == "__main__":
    unittest.main()
