import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.storage.database import ProductionDatabase, StorageSettings
from fam_os.product.tool_loop import (
    BoundedToolLoop, ToolLoopRepository, ToolRegistry, ToolResult, ToolStep,
)


class ToolLoopTests(unittest.TestCase):
    def test_runs_multiple_steps_retries_and_persists_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = ProductionDatabase(StorageSettings(
                Path(temporary) / "fam.sqlite3", os.geteuid(),
            ))
            database.open()
            database.execute(
                "INSERT INTO useful_tasks(task_id,workflow_id,prompt,workspace_root,status,"
                "created_at,updated_at,summary,error,continuation_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("task", "test", "prompt", temporary, "running", "now", "now", None, None, None),
            )
            calls = {"flaky": 0}
            registry = ToolRegistry()
            registry.register("observe", lambda args: ToolResult({"seen": args["path"]}))

            def flaky(_args):
                calls["flaky"] += 1
                if calls["flaky"] == 1:
                    raise RuntimeError("temporary")
                return ToolResult({"changed": True})

            registry.register("change", flaky)
            repository = ToolLoopRepository(database)
            results = BoundedToolLoop(registry, repository).run("task", (
                ToolStep("observe", "observe", {"path": "README.md"}),
                ToolStep("change", "change", {}, maximum_attempts=2),
            ))
            self.assertEqual(2, len(results))
            timeline = repository.timeline("task")
            self.assertEqual(["completed", "failed", "completed"], [item["status"] for item in timeline])
            database.close()

    def test_refuses_unbounded_or_unknown_work(self) -> None:
        registry = ToolRegistry()
        with self.assertRaisesRegex(ValueError, "one and 64"):
            BoundedToolLoop(registry, None).run("task", ())


if __name__ == "__main__":
    unittest.main()
