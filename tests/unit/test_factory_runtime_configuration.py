"""Installed Expert Factory configuration and service composition tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fam_os.product.factory_runtime_configuration import (
    FactoryRuntimeConfiguration,
    FactoryRuntimeConfigurationStore,
)
from fam_os.product.service_cli import (
    _factory_evaluation_settings,
    _factory_release_settings,
    _factory_training_settings,
)


class FactoryRuntimeConfigurationTests(unittest.TestCase):
    def test_private_configuration_composes_all_installed_factory_backends(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            configuration = _configuration(root)
            store = FactoryRuntimeConfigurationStore(
                root / "state/config/factory-runtime.json", os.geteuid(),
            )
            self.assertEqual(configuration, store.save(configuration))
            self.assertEqual(configuration, store.load())
            self.assertEqual(
                0o600,
                (root / "state/config/factory-runtime.json").stat().st_mode
                & 0o777,
            )
            args = SimpleNamespace(
                ollama_executable=root / "ollama",
                ollama_url="http://127.0.0.1:11435",
            )
            parser = SimpleNamespace(error=lambda message: self.fail(message))
            self.assertIsNotNone(_factory_training_settings(
                args, root / "state", parser, configuration,
            ))
            self.assertIsNotNone(_factory_evaluation_settings(
                args, root / "state", parser, configuration,
            ))
            release = _factory_release_settings(
                args, root / "state", parser, configuration,
            )
            self.assertEqual(
                configuration.llama_cpp_revision,
                release.llama_cpp_revision,
            )

    def test_configuration_rejects_missing_pinned_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            configuration = _configuration(root)
            Path(configuration.canary_suite).unlink()
            store = FactoryRuntimeConfigurationStore(
                root / "state/config/factory-runtime.json", os.geteuid(),
            )
            with self.assertRaisesRegex(ValueError, "unavailable"):
                store.save(configuration)


def _configuration(root: Path) -> FactoryRuntimeConfiguration:
    directories = tuple(root / name for name in (
        "training-environment", "training-model", "conversion-environment",
        "llama.cpp", "conversion-model",
    ))
    for directory in directories:
        directory.mkdir()
    files = tuple(root / name for name in (
        "training-wheelhouse.json", "evaluation.jsonl",
        "conversion-wheelhouse.json", "canary.jsonl",
    ))
    for path in files:
        path.write_text("{}\n")
    return FactoryRuntimeConfiguration(
        training_environment_directory=str(directories[0]),
        training_wheelhouse_manifest=str(files[0]),
        training_model_directory=str(directories[1]),
        evaluation_suite=str(files[1]),
        conversion_environment_directory=str(directories[2]),
        conversion_wheelhouse_manifest=str(files[2]),
        llama_cpp_directory=str(directories[3]),
        llama_cpp_revision="a" * 40,
        conversion_model_directory=str(directories[4]),
        canary_suite=str(files[3]),
        allowed_licenses=("Apache-2.0",),
    )


if __name__ == "__main__":
    unittest.main()
