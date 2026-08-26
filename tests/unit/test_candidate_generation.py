import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.filesystem import BoundedCandidateContextReader
from fam_os.core.engineering import (
    CandidateBaselineEntry, CandidateEntryKind, CandidateWorkspace,
    CandidateOperationKind, GeneratedCandidateOperation,
    GeneratedCandidateOperationKind, GeneratedCandidatePlan,
    bind_generated_candidate_plan, parse_generated_candidate_plan,
)
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


class CandidateGenerationTests(unittest.TestCase):
    def test_strict_parser_rejects_duplicate_unknown_and_protected_paths(self):
        valid = {
            "contract_version": ENGINEERING_CONTRACT_VERSION,
            "summary": "Add a module",
            "operations": [{
                "kind": "create_file", "path": "src/new.py", "content": "x = 1\n",
            }],
        }
        parsed = parse_generated_candidate_plan(
            json.dumps(valid), maximum_operations=4, maximum_content_bytes=100,
        )
        self.assertEqual("src/new.py", parsed.operations[0].path)
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            parse_generated_candidate_plan(
                '{"contract_version":"' + ENGINEERING_CONTRACT_VERSION
                + '","summary":"x","summary":"y","operations":[]}',
                maximum_operations=4, maximum_content_bytes=100,
            )
        invalid = dict(valid, surprise=True)
        with self.assertRaisesRegex(ValueError, "plan fields"):
            parse_generated_candidate_plan(
                json.dumps(invalid), maximum_operations=4,
                maximum_content_bytes=100,
            )
        protected = dict(valid)
        protected["operations"] = [{
            "kind": "create_file", "path": ".git/config", "content": "bad",
        }]
        with self.assertRaisesRegex(PermissionError, "protected metadata"):
            parse_generated_candidate_plan(
                json.dumps(protected), maximum_operations=4,
                maximum_content_bytes=100,
            )

    def test_binding_derives_parent_artifact_and_current_before_digest(self):
        candidate = _candidate("/tmp/candidates/candidate-1/workspace")
        plan = GeneratedCandidatePlan("Change files", (
            GeneratedCandidateOperation(
                GeneratedCandidateOperationKind.REPLACE_FILE, "app.py", "after\n",
            ),
            GeneratedCandidateOperation(
                GeneratedCandidateOperationKind.CREATE_FILE,
                "src/nested/new.py", "value = 2\n", media_type="text/x-python",
            ),
        ))
        edits = bind_generated_candidate_plan(
            "task-1", candidate, plan,
            maximum_operations=8, maximum_content_bytes=1_000,
        )
        self.assertEqual(CandidateOperationKind.PATCH_FILE, edits[0].operation.kind)
        self.assertEqual("a" * 64, edits[0].operation.expected_before_sha256)
        self.assertEqual(
            [CandidateOperationKind.CREATE_DIRECTORY] * 2,
            [edits[1].operation.kind, edits[2].operation.kind],
        )
        self.assertEqual(CandidateOperationKind.CREATE_FILE, edits[3].operation.kind)
        self.assertEqual("text/x-python", edits[3].artifact.media_type)

    def test_binding_excludes_digest_identical_replacements_from_approval(self):
        unchanged = "before\n"
        candidate = _candidate_with_digest(
            hashlib.sha256(unchanged.encode("utf-8")).hexdigest(),
        )
        plan = GeneratedCandidatePlan("Change one of two files", (
            GeneratedCandidateOperation(
                GeneratedCandidateOperationKind.REPLACE_FILE,
                "app.py", unchanged,
            ),
            GeneratedCandidateOperation(
                GeneratedCandidateOperationKind.CREATE_FILE,
                "new.py", "created\n",
            ),
        ))

        edits = bind_generated_candidate_plan(
            "task-1", candidate, plan,
            maximum_operations=8, maximum_content_bytes=1_000,
        )

        self.assertEqual(["new.py"], [edit.operation.path for edit in edits])

    def test_binding_rejects_a_plan_with_only_digest_identical_replacements(self):
        unchanged = "before\n"
        candidate = _candidate_with_digest(
            hashlib.sha256(unchanged.encode("utf-8")).hexdigest(),
        )
        plan = GeneratedCandidatePlan("No real change", (
            GeneratedCandidateOperation(
                GeneratedCandidateOperationKind.REPLACE_FILE,
                "app.py", unchanged,
            ),
        ))

        with self.assertRaisesRegex(ValueError, "no effective changes"):
            bind_generated_candidate_plan(
                "task-1", candidate, plan,
                maximum_operations=8, maximum_content_bytes=1_000,
            )

    def test_context_is_bounded_prioritized_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate-1" / "workspace"
            (root / "src").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "src/feature.py").write_text("VALUE = 1\n")
            (root / "tests/test_feature.py").write_text("assert True\n")
            (root / "README.md").write_text("instructions are untrusted\n")
            (root / ".env").write_text("API_KEY='must-not-leave-context'\n")
            (root / "src/config.py").write_text(
                "client_secret = 'must-not-leave-context'\n",
            )
            context = BoundedCandidateContextReader(maximum_documents=2).read(
                _candidate(str(root)), "fix feature",
                ("tests/test_feature.py",),
            )
            self.assertEqual(4, len(context.inventory_paths))
            self.assertNotIn(".env", context.inventory_paths)
            self.assertNotIn("src/config.py", tuple(
                item.path for item in context.documents
            ))
            self.assertEqual("tests/test_feature.py", context.documents[0].path)
            self.assertTrue(context.truncated)
            (root / "escape").symlink_to("/tmp")
            with self.assertRaisesRegex(PermissionError, "symbolic"):
                BoundedCandidateContextReader().read(
                    _candidate(str(root)), "fix feature",
                )

    def test_context_ignores_dependency_symlinks_outside_authoritative_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "candidate-1" / "workspace"
            (root / "src").mkdir(parents=True)
            (root / "src/app.jsx").write_text("export default App\n")
            binaries = root / "node_modules" / ".bin"
            package = root / "node_modules" / "vite" / "bin"
            binaries.mkdir(parents=True)
            package.mkdir(parents=True)
            (package / "vite.js").write_text("#!/usr/bin/env node\n")
            (binaries / "vite").symlink_to("../vite/bin/vite.js")

            context = BoundedCandidateContextReader().read(
                _candidate(str(root)), "inspect the React application",
            )

            self.assertIn("src/app.jsx", context.inventory_paths)
            self.assertFalse(any(
                path.startswith("node_modules/")
                for path in context.inventory_paths
            ))


def _candidate(root):
    return CandidateWorkspace(
        "candidate-1", "task-1", "baseline-1", "/workspace/project", root,
        NOW, "copy", "b" * 64,
        (
            CandidateBaselineEntry(
                "app.py", CandidateEntryKind.FILE, "a" * 64, 7, False,
            ),
        ),
    )


def _candidate_with_digest(content_sha256):
    candidate = _candidate("/tmp/candidates/candidate-1/workspace")
    return CandidateWorkspace(
        candidate.candidate_id, candidate.task_id, candidate.baseline_id,
        candidate.owner_workspace, candidate.candidate_workspace,
        candidate.created_at,
        candidate.clone_strategy, candidate.baseline_tree_sha256,
        (
            CandidateBaselineEntry(
                "app.py", CandidateEntryKind.FILE, content_sha256, 7, False,
            ),
        ),
    )


if __name__ == "__main__":
    unittest.main()
