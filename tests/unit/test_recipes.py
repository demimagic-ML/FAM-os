import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.recipes import RecipeLibrary
from fam_os.product.storage.database import ProductionDatabase, StorageSettings


class _Tasks:
    def __init__(self): self.requests = []
    def run(self, request):
        self.requests.append(request)
        return {"task_id": "task-1", "status": "completed", "request": request}


class RecipeTests(unittest.TestCase):
    def test_ten_builtins_and_custom_recipe_can_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = ProductionDatabase(StorageSettings(
                Path(temporary) / "fam.sqlite3", os.geteuid(),
            ))
            database.open()
            tasks = _Tasks()
            library = RecipeLibrary(database, tasks)
            self.assertEqual(10, len(library.list()["recipes"]))
            custom = library.create({
                "name": "Monthly report", "description": "Profile monthly values",
                "request_template": {
                    "workflow_id": "data.analyze-csv", "prompt": "Analyze monthly KPIs",
                },
            })
            result = library.run(custom["recipe_id"], {"workspace_root": temporary})
            self.assertEqual("completed", result["status"])
            self.assertEqual("data.analyze-csv", tasks.requests[0]["workflow_id"])
            edited = library.update(custom["recipe_id"], {"name": "Quarterly report"})
            self.assertEqual("Quarterly report", edited["name"])
            database.close()


if __name__ == "__main__":
    unittest.main()
