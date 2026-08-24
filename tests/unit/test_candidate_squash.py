import hashlib
import unittest
from datetime import datetime, timezone

from fam_os.core.engineering import (
    CandidateArtifact,
    CandidateBaselineEntry,
    CandidateContentKind,
    CandidateEditRecord,
    CandidateEditStatus,
    CandidateEntryKind,
    CandidateOperation,
    CandidateOperationKind,
    CandidateWorkspace,
    squash_candidate_edits,
)


NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


class CandidateSquashTests(unittest.TestCase):
    def test_repair_edits_collapse_to_one_owner_baseline_patch(self):
        old = _digest(b"VALUE = 1\n")
        intermediate = _digest(b"VALUE = 2\n")
        final = _digest(b"VALUE = 3\n")
        candidate = _candidate((
            _entry("app.py", CandidateEntryKind.FILE, old, 10, False),
        ))
        current = (
            _entry("app.py", CandidateEntryKind.FILE, final, 10, True),
        )
        edits = (
            _edit("first", _content_operation(
                "first", "app.py", old, intermediate,
            ), intermediate),
            _edit("repair", _content_operation(
                "repair", "app.py", intermediate, final,
            ), final),
        )

        operations, artifacts = squash_candidate_edits(
            "task-1", candidate, current, edits,
            maximum_operations=4, maximum_content_bytes=100,
        )

        self.assertEqual(1, len(operations))
        self.assertEqual(CandidateOperationKind.PATCH_FILE, operations[0].kind)
        self.assertEqual(old, operations[0].expected_before_sha256)
        self.assertEqual(final, artifacts[0].content_sha256)
        self.assertEqual(CandidateContentKind.TEXT, artifacts[0].content_kind)

    def test_unauthorized_final_build_output_is_rejected(self):
        old = _digest(b"VALUE = 1\n")
        final = _digest(b"VALUE = 2\n")
        generated = _digest(b"generated\n")
        candidate = _candidate((
            _entry("app.py", CandidateEntryKind.FILE, old, 10, False),
        ))
        current = (
            _entry("app.py", CandidateEntryKind.FILE, final, 10, False),
            _entry("build/output.txt", CandidateEntryKind.FILE, generated, 10, False),
        )
        edits = (_edit(
            "first", _content_operation("first", "app.py", old, final), final,
        ),)

        with self.assertRaisesRegex(PermissionError, "unauthorized path"):
            squash_candidate_edits(
                "task-1", candidate, current, edits,
                maximum_operations=4, maximum_content_bytes=100,
            )

    def test_created_directories_precede_files_and_binary_is_typed(self):
        image = _digest(b"\x89PNG\r\n")
        candidate = _candidate(())
        current = (
            _entry("assets", CandidateEntryKind.DIRECTORY, None, 0, False),
            _entry("assets/icon.png", CandidateEntryKind.FILE, image, 6, False),
        )
        edits = (
            _edit("directory", CandidateOperation(
                "operation-directory", CandidateOperationKind.CREATE_DIRECTORY,
                "assets",
            )),
            _edit("file", CandidateOperation(
                "operation-file", CandidateOperationKind.CREATE_FILE,
                "assets/icon.png", artifact_id="artifact-source",
            ), image, artifact_id="artifact-source"),
        )

        operations, artifacts = squash_candidate_edits(
            "task-1", candidate, current, edits,
            maximum_operations=4, maximum_content_bytes=100,
        )

        self.assertEqual(
            (CandidateOperationKind.CREATE_DIRECTORY, CandidateOperationKind.CREATE_FILE),
            tuple(item.kind for item in operations),
        )
        self.assertEqual(CandidateContentKind.BINARY, artifacts[0].content_kind)
        self.assertEqual("image/png", artifacts[0].media_type)

    def test_no_change_and_in_place_entry_kind_change_are_rejected(self):
        old = _digest(b"VALUE = 1\n")
        entry = _entry("app.py", CandidateEntryKind.FILE, old, 10, False)
        candidate = _candidate((entry,))
        edit = _edit(
            "delete", CandidateOperation(
                "operation-delete", CandidateOperationKind.DELETE,
                "app.py", old,
            ),
        )

        with self.assertRaisesRegex(ValueError, "no final changes"):
            squash_candidate_edits(
                "task-1", candidate, (entry,), (edit,),
                maximum_operations=4, maximum_content_bytes=100,
            )
        with self.assertRaisesRegex(RuntimeError, "entry kind"):
            squash_candidate_edits(
                "task-1", candidate,
                (_entry("app.py", CandidateEntryKind.DIRECTORY, None, 0, False),),
                (edit,), maximum_operations=4, maximum_content_bytes=100,
            )


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _entry(path, kind, digest, size, executable):
    return CandidateBaselineEntry(path, kind, digest, size, executable)


def _candidate(entries):
    return CandidateWorkspace(
        "candidate-1", "task-1", "baseline-1", "/workspace/project",
        "/tmp/candidate-1/workspace", NOW, "copy", "b" * 64, entries,
    )


def _content_operation(name, path, before, after):
    return CandidateOperation(
        f"operation-{name}", CandidateOperationKind.PATCH_FILE, path, before,
        f"artifact-{after}",
    )


def _edit(name, operation, after=None, *, artifact_id=None):
    artifact = None
    if operation.artifact_id is not None:
        artifact = CandidateArtifact(
            artifact_id or operation.artifact_id, CandidateContentKind.TEXT,
            "text/plain", after or "a" * 64, 10, "test",
        )
    return CandidateEditRecord(
        f"edit-{name}", "definition-1", "task-1", "candidate-1",
        "session-1", "owner-1", operation, artifact,
        (f"authorization-{name}",), 10, CandidateEditStatus.APPLIED, 1,
        NOW, NOW, after_sha256=after,
    )


if __name__ == "__main__":
    unittest.main()
