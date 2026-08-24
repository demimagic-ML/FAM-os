"""Focused tests for the product-reachable specialist release composition."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fam_os.product.composition.factory_release import FactoryReleaseRuntimeSettings
from fam_os.product.factory_conversion import ProductFactoryConversions


class _Backend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def run(self, *, approval_id: str, confirmed: bool):
        self.calls.append((approval_id, confirmed))
        return "receipt"


class FactoryReleaseCompositionTests(unittest.TestCase):
    def test_slots_settings_validate_all_path_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).absolute()
            settings = FactoryReleaseRuntimeSettings(
                conversion_environment=root / "environment",
                conversion_wheelhouse_manifest=root / "wheelhouse.json",
                llama_cpp_directory=root / "llama.cpp",
                llama_cpp_revision="a" * 40,
                model_directory=root / "model",
                training_workspace_root=root / "training",
                conversion_workspace_root=root / "conversion",
                package_output_root=root / "output",
                package_artifact_root=root / "artifacts",
                package_lifecycle_state=root / "lifecycle.json",
                canary_workspace_root=root / "canary",
                canary_suite=root / "canary.jsonl",
                ollama_executable=root / "ollama",
                ollama_url="http://127.0.0.1:11435",
            )
            self.assertEqual(settings.llama_cpp_revision, "a" * 40)

    def test_relative_release_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).absolute()
            with self.assertRaisesRegex(ValueError, "paths must be absolute"):
                FactoryReleaseRuntimeSettings(
                    conversion_environment=Path("relative"),
                    conversion_wheelhouse_manifest=root / "wheelhouse.json",
                    llama_cpp_directory=root / "llama.cpp",
                    llama_cpp_revision="a" * 40,
                    model_directory=root / "model",
                    training_workspace_root=root / "training",
                    conversion_workspace_root=root / "conversion",
                    package_output_root=root / "output",
                    package_artifact_root=root / "artifacts",
                    package_lifecycle_state=root / "lifecycle.json",
                    canary_workspace_root=root / "canary",
                    canary_suite=root / "canary.jsonl",
                    ollama_executable=root / "ollama",
                    ollama_url="http://127.0.0.1:11435",
                )

    def test_conversion_facade_dispatches_to_composed_backend(self) -> None:
        backend = _Backend()
        conversions = ProductFactoryConversions(
            object(), object(), backend=backend,
        )
        receipt = conversions.run(
            approval_id="conversion-approval-1", confirmed=True,
        )
        self.assertEqual(receipt, "receipt")
        self.assertEqual(backend.calls, [("conversion-approval-1", True)])

    def test_conversion_facade_refuses_missing_backend(self) -> None:
        conversions = ProductFactoryConversions(object(), object())
        with self.assertRaisesRegex(RuntimeError, "backend is not configured"):
            conversions.run(
                approval_id="conversion-approval-1", confirmed=True,
            )


if __name__ == "__main__":
    unittest.main()
