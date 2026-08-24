import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.shell import (
    ShellAskCommand,
    ShellEngineeringLoopOperation,
    ShellEngineeringLoopQuery,
    ShellRunState,
)
from tests.integration.product_runtime_fixture import ResidentRuntimeFixture


class ProductServiceStorageModeTests(unittest.TestCase):
    def test_new_product_service_creates_secure_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = LocalProductService(
                ProductServiceSettings(root / "state", root / "runtime", console_port=0),
                runtime=_UnusedRuntime(),
            )
            service.start()
            try:
                self.assertTrue((root / "state/state/fam.sqlite3").is_file())
                self.assertTrue((root / "state/state/master.key").is_file())
                self.assertFalse((root / "state/recovery/enabled").exists())
                self.assertIsNotNone(service.engineering_loop_api)
                self.assertIs(
                    service.engineering_loop_api,
                    service.console_server.engineering_loop_api,
                )
                client = UnixShellCoreClient(
                    UnixShellClientConfiguration(root / "runtime/shell.sock"),
                )
                response = client.engineering_loop_query(
                    ShellEngineeringLoopQuery(
                        "loop-list-1", ShellEngineeringLoopOperation.LIST,
                        service.engineering_loop_api.owner_id,
                    )
                )
                self.assertEqual((), response.views)
                self.assertTrue(
                    (root / "state/state/engineering-loop.sqlite3").is_file()
                )
            finally:
                service.stop()

    def test_missing_key_for_existing_database_serves_recovery_failure_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "state/state/fam.sqlite3"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"existing encrypted state")
            service = LocalProductService(
                ProductServiceSettings(root / "state", root / "runtime", console_port=0),
                runtime=_UnusedRuntime(),
            )
            service.start()
            try:
                client = UnixShellCoreClient(
                    UnixShellClientConfiguration(root / "runtime/shell.sock"),
                )
                snapshot = client.ask(ShellAskCommand("request-1", "do work"))
                self.assertEqual(ShellRunState.TERMINAL, snapshot.state)
                self.assertIn("recovery mode", snapshot.result.reason)
                self.assertTrue((root / "state/recovery/enabled").is_file())
                self.assertFalse((root / "state/state/master.key").exists())
            finally:
                service.stop()


class _UnusedRuntime(ResidentRuntimeFixture):
    def chat(self, _request):
        raise AssertionError("inference must not run in this test")


if __name__ == "__main__":
    unittest.main()
