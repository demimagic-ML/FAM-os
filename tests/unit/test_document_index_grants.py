import unittest
from datetime import UTC, datetime, timedelta

from fam_os.memory import (
    DocumentIndexGrant,
    DocumentIndexGrantKind,
    DocumentIndexReceipt,
    MemoryScope,
)


NOW = datetime(2026, 7, 17, tzinfo=UTC)


def grant(**changes):
    values = {
        "grant_id": "grant-1",
        "root_path": "/home/user/project",
        "kind": DocumentIndexGrantKind.FOLDER,
        "scope": MemoryScope("owner", ("assist",), workspace_ids=("workspace",)),
        "recursive": True,
        "allowed_extensions": (".md", ".txt"),
        "max_files": 64,
        "max_file_bytes": 1_048_576,
        "max_total_bytes": 8_388_608,
        "approved_by": "owner",
        "approved_at": NOW,
        "expires_at": NOW + timedelta(days=7),
        "embedding_model_ref": "nomic-embed-text:latest",
        "embedding_artifact_sha256": "a" * 64,
    }
    values.update(changes)
    return DocumentIndexGrant(**values)


class DocumentIndexGrantTests(unittest.TestCase):
    def test_grant_is_explicit_bounded_and_expires(self):
        value = grant()
        self.assertTrue(value.active_at(NOW))
        self.assertFalse(value.active_at(value.expires_at))

    def test_unsafe_or_unbounded_grants_are_rejected(self):
        cases = (
            {"root_path": "relative/path"},
            {"root_path": "/home/user/../other"},
            {"allowed_extensions": (".TXT",)},
            {"max_files": 0},
            {"expires_at": NOW + timedelta(days=91)},
            {"kind": DocumentIndexGrantKind.FILE, "recursive": True},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                grant(**changes)

    def test_receipt_pass_is_derived_from_indexed_records(self):
        value = DocumentIndexReceipt(
            "receipt", "grant-1", ("doc",), 1, 42, (),
            NOW, NOW + timedelta(days=1), True,
        )
        self.assertTrue(value.passed)
        with self.assertRaisesRegex(ValueError, "derive"):
            DocumentIndexReceipt(
                "receipt", "grant-1", (), 0, 0, (),
                NOW, NOW + timedelta(days=1), True,
            )


if __name__ == "__main__":
    unittest.main()
