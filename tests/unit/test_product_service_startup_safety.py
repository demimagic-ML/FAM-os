"""Startup-path bounds and partial-composition cleanup regressions."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from fam_os.adapters.codex_subscription import CodexSubscriptionSettings
from fam_os.product.service import (
    LocalProductService, ProductServiceSettings, _engineering_model_ref,
)


class ProductServiceStartupSafetyTests(unittest.TestCase):
    def test_engineering_prefers_stronger_installed_agent_model(self) -> None:
        runtime = Mock()
        runtime.available_models.return_value = (
            "qwen2.5-coder:7b", "qwen3-coder:30b",
        )

        self.assertEqual(
            "qwen3-coder:30b",
            _engineering_model_ref(runtime, "qwen2.5-coder:7b", None),
        )

    def test_explicit_engineering_model_overrides_discovery(self) -> None:
        self.assertEqual(
            "custom-agent:latest",
            _engineering_model_ref(Mock(), "fallback", "custom-agent:latest"),
        )

    def test_runtime_root_rejects_linux_unix_socket_overflow(self) -> None:
        runtime_root = Path("/tmp") / ("x" * 100)

        with self.assertRaisesRegex(ValueError, "AF_UNIX"):
            ProductServiceSettings(Path("/tmp/state"), runtime_root)

    def test_partial_startup_does_not_shutdown_unserved_console(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = LocalProductService(ProductServiceSettings(
                root / "state", root / "run",
            ))
            console = Mock()
            service.console_server = console

            service.stop()

            console.shutdown.assert_not_called()
            console.server_close.assert_called_once_with()
            self.assertIsNone(service.console_server)

    def test_codex_inference_work_root_cannot_escape_private_runtime(self) -> None:
        with self.assertRaisesRegex(ValueError, "private runtime root"):
            ProductServiceSettings(
                Path("/tmp/state"), Path("/tmp/runtime"),
                codex_subscription=CodexSubscriptionSettings(
                    Path("/usr/bin/python3"), Path("/tmp/elsewhere"),
                    Path("/tmp"),
                ),
            )


if __name__ == "__main__":
    unittest.main()
