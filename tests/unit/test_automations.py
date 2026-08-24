import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.automations import AutomationService
from fam_os.product.storage.database import ProductionDatabase, StorageSettings


class _Tasks:
    def __init__(self, database):
        self.database = database
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        task_id = f"task-{len(self.requests)}"
        self.database.execute(
            "INSERT INTO useful_tasks(task_id,workflow_id,prompt,workspace_root,status,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (task_id, "test", "test", "/tmp", "completed", "now", "now"),
        )
        return {"task_id": task_id, "status": "completed"}


class AutomationTests(unittest.TestCase):
    def test_manual_automation_runs_saved_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = _database(temporary)
            tasks = _Tasks(database)
            service = AutomationService(database, tasks)
            automation = service.create({
                "name": "Weekly CSV report",
                "request": {
                    "workflow_id": "data.analyze-csv", "prompt": "Analyze",
                    "workspace_root": temporary,
                },
                "trigger": {"type": "manual"}, "run_mode": "single",
            })
            result = service.run_now(automation["automation_id"])
            self.assertEqual("completed", result["status"])
            self.assertEqual("task-1", service.inspect(automation["automation_id"])["last_task_id"])
            self.assertEqual("completed", service.runs(automation["automation_id"])["runs"][0]["status"])
            self.assertEqual("task-1", service.notifications()["notifications"][0]["task_id"])
            database.close()

    def test_file_change_trigger_runs_only_after_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            watched = root / "input.csv"
            watched.write_text("a,b\n1,2\n")
            database = _database(temporary)
            tasks = _Tasks(database)
            service = AutomationService(database, tasks)
            service.create({
                "name": "Watch CSV", "request": {"workflow_id": "data.analyze-csv"},
                "trigger": {"type": "file_changed", "path": str(watched)},
                "condition": {"suffix": ".csv"}, "run_mode": "queued",
            })
            self.assertEqual((), service.tick())
            watched.write_text("a,b\n3,4\n5,6\n")
            results = service.tick()
            self.assertEqual(1, len(results))
            self.assertEqual(1, len(tasks.requests))
            database.close()

    def test_short_interval_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = _database(temporary)
            with self.assertRaisesRegex(ValueError, "at least 60"):
                AutomationService(database, _Tasks(database)).create({
                    "name": "Too frequent", "request": {},
                    "trigger": {"type": "interval", "seconds": 5},
                })
            database.close()


def _database(root):
    database = ProductionDatabase(StorageSettings(
        Path(root) / "state/fam.sqlite3", os.geteuid(),
    ))
    database.open()
    return database


if __name__ == "__main__":
    unittest.main()
