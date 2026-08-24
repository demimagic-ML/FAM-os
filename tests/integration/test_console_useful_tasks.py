import http.cookiejar
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider
from fam_os.product.storage.database import ProductionDatabase, StorageSettings
from fam_os.product.useful_tasks import UsefulTaskApi, UsefulTaskRepository


class ConsoleUsefulTaskTests(unittest.TestCase):
    def test_catalog_run_history_and_ui_are_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "values.csv").write_text("name,value\na,2\nb,4\n")
            database = ProductionDatabase(
                StorageSettings(root / "state/fam.sqlite3", os.geteuid()),
            )
            database.open()
            api = UsefulTaskApi(UsefulTaskRepository(database), identifier=lambda: "useful-1")
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(root), "x" * 32,
                useful_task_api=api,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                opener, csrf = _authenticated(base)
                catalog = json.loads(opener.open(base + "/api/v1/useful/workflows").read())
                self.assertEqual(5, len(catalog["workflows"]))
                request = urllib.request.Request(
                    base + "/api/v1/useful/tasks", method="POST",
                    data=json.dumps({
                        "workflow_id": "data.analyze-csv",
                        "prompt": "Analyze values",
                        "workspace_root": str(workspace),
                    }).encode(),
                    headers={
                        "Content-Type": "application/json", "Origin": base,
                        "X-CSRF-Token": csrf,
                    },
                )
                result = json.loads(opener.open(request).read())
                self.assertEqual("completed", result["status"])
                history = json.loads(opener.open(base + "/api/v1/useful/tasks").read())
                self.assertEqual("useful-1", history["tasks"][0]["task_id"])
                page = opener.open(base).read()
                script = opener.open(base + "/useful_tasks.js").read()
                self.assertIn(b"Useful workflows", page)
                self.assertIn(b"/api/v1/useful/tasks", script)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                database.close()


def _authenticated(base: str):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    exchange = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
    )
    session = json.loads(opener.open(exchange).read())
    return opener, session["csrf_token"]


if __name__ == "__main__":
    unittest.main()
