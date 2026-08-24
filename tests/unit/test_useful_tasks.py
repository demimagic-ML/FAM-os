import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fam_os.product.storage.database import ProductionDatabase, StorageSettings
from fam_os.product.useful_tasks import UsefulTaskApi, UsefulTaskRepository
from fam_os.product.tool_loop import ToolLoopRepository


class UsefulTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = ProductionDatabase(
            StorageSettings(self.root / "state/fam.sqlite3", os.geteuid()),
        )
        self.database.open()
        self.counter = 0

    def tearDown(self) -> None:
        self.database.close()
        self.temporary.cleanup()

    def api(self, **values) -> UsefulTaskApi:
        def identifier():
            self.counter += 1
            return f"task-{self.counter}"
        return UsefulTaskApi(
            UsefulTaskRepository(self.database), identifier=identifier,
            clock=lambda: datetime(2026, 8, 24, tzinfo=timezone.utc),
            tool_loop_repository=ToolLoopRepository(self.database), **values,
        )

    def test_csv_workflow_creates_report_chart_and_durable_history(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()
        (workspace / "sales.csv").write_text(
            "month,revenue,cost\nJan,12,7\nFeb,18,9\n", encoding="utf-8",
        )
        api = self.api()
        result = api.run({
            "workflow_id": "data.analyze-csv",
            "prompt": "Analyze sales",
            "workspace_root": str(workspace),
        })
        self.assertEqual("completed", result["status"])
        self.assertEqual(2, len(result["artifacts"]))
        paths = {Path(item["path"]) for item in result["artifacts"]}
        self.assertEqual({"analysis.md", "chart.svg"}, {item.name for item in paths})
        self.assertTrue(all(item.is_file() for item in paths))
        self.assertEqual("task-1", api.list()["tasks"][0]["task_id"])
        self.assertEqual(
            ["validate", "execute"],
            [item["step_id"] for item in api.timeline("task-1")["steps"]],
        )
        retried = api.retry("task-1")
        self.assertEqual("task-1", retried["parent_task_id"])
        forked = api.fork("task-1", {"prompt": "Compare revenue and cost"})
        self.assertEqual("Compare revenue and cost", forked["prompt"])
        report = next(item for item in result["artifacts"] if item["kind"] == "report")
        preview = api.artifact_document(report["artifact_id"])
        self.assertIn("CSV analysis", preview["content"])

    def test_audio_workflow_uses_local_recognizer(self) -> None:
        workspace = self.root / "audio"
        workspace.mkdir()
        (workspace / "meeting.wav").write_bytes(b"RIFF-fake-test-audio")
        recognizer = SimpleNamespace(transcribe=lambda path: SimpleNamespace(
            text="Decide the launch date. Alice owns the follow-up.",
            model_ref="test-whisper", language="en", artifact_sha256="a" * 64,
        ))
        result = self.api(recognizer=recognizer).run({
            "workflow_id": "media.transcribe-audio",
            "prompt": "Transcribe and extract action items",
            "workspace_root": str(workspace),
        })
        self.assertEqual("completed", result["status"])
        transcript = Path(result["artifacts"][0]["path"]).read_text()
        self.assertIn("Alice owns the follow-up", transcript)

    def test_engineering_workflow_delegates_to_existing_lifecycle(self) -> None:
        workspace = self.root / "repo"
        workspace.mkdir()
        calls = []
        api = self.api(engineering_delegate=lambda prompt, root: (
            calls.append((prompt, root)) or {"proposal_id": "proposal-1", "state": "proposed"}
        ))
        result = api.run({
            "workflow_id": "engineering.issue-to-change",
            "prompt": "Fix issue 42 and run tests",
            "workspace_root": str(workspace),
        })
        self.assertEqual("completed", result["status"])
        self.assertEqual([("Fix issue 42 and run tests", str(workspace))], calls)
        self.assertEqual("proposal-1", result["continuation"]["proposal_id"])

    def test_failure_is_retained_as_a_visible_task(self) -> None:
        workspace = self.root / "empty"
        workspace.mkdir()
        api = self.api()
        result = api.run({
            "workflow_id": "documents.summarize-pdf",
            "prompt": "Summarize PDFs",
            "workspace_root": str(workspace),
        })
        self.assertEqual("failed", result["status"])
        self.assertIn("no matching input files", result["error"])

    def test_catalog_exposes_all_five_workflows(self) -> None:
        self.assertEqual(5, len(self.api().workflows()))


if __name__ == "__main__":
    unittest.main()
