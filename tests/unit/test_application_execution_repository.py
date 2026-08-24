import os
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from fam_os.core.admission import AdmittedTaskRequest, RequestPermissionContext
from fam_os.core.contracts import TaskRequest
from fam_os.core.production.application_contracts import (
    ApplicationExecutionRecord,
    ApplicationExecutionState,
)
from fam_os.core.routing import RoutedTaskRequest
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings
from fam_os.routing import RouteDecision, RouteName, RoutingResult
from tests.contract.schema_application_fixtures import NOW, observation_result


class ApplicationExecutionRepositoryTests(unittest.TestCase):
    def test_encrypted_state_uses_revision_compare_and_swap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
            opened = SecureStorage(
                database, OwnerKeyStore(root / "master.key", os.geteuid()),
            ).open()
            repositories = CoreStorageComposition(
                database, opened.cipher, str(os.geteuid()),
            ).repositories()
            repository = repositories.application_executions
            record = ApplicationExecutionRecord(
                "task-request-1", "request-1", _routed(), "instance-1",
                "file:///workspace/main.py", "grant-1",
                ApplicationExecutionState.ACTIVE, 0,
            )
            self.assertTrue(repositories.requests.add(
                record.routed.admitted.request, "running",
            ))
            self.assertTrue(repository.create(record))
            updated = replace(
                record, revision=1, observations=(observation_result(),),
                reversal_session_id="task-undo-1",
            )
            self.assertTrue(repository.replace(0, updated))
            self.assertFalse(repository.replace(0, replace(updated, revision=2)))
            self.assertEqual(updated, repository.get(record.instance_id))
            database.close()


def _routed():
    capabilities = ("vscode.editor.active",)
    request = TaskRequest("request-1", "Observe editor", capabilities)
    permission = RequestPermissionContext(
        "local-owner", "shell-request-1", "authority-request-1",
        capabilities, NOW + timedelta(hours=1),
    )
    admitted = AdmittedTaskRequest("admission-request-1", request, permission, NOW)
    decision = RouteDecision(RouteName.CODE, 1.0, "Application task", capabilities)
    return RoutedTaskRequest(admitted, RoutingResult(decision))


if __name__ == "__main__":
    unittest.main()
