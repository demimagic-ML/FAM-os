import json
import tempfile
import unittest
from pathlib import Path

from tools.phase22_training_environment.wheel_manifest import (
    build_manifest,
    verify_manifest,
)


class FactoryTrainingWheelhouseTests(unittest.TestCase):
    def test_manifest_binds_requirements_every_wheel_and_its_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            requirements = root / "requirements.txt"
            requirements.write_text("torch==2.13.0\n", encoding="utf-8")
            wheelhouse = root / "wheels"
            wheelhouse.mkdir()
            wheel = wheelhouse / "torch-2.13.0-py3-none-any.whl"
            wheel.write_bytes(b"first wheel content")
            document = build_manifest(requirements, wheelhouse)
            verify_manifest(
                json.loads(json.dumps(document)), requirements, wheelhouse,
            )
            wheel.write_bytes(b"changed wheel content")
            with self.assertRaisesRegex(ValueError, "files changed"):
                verify_manifest(document, requirements, wheelhouse)

    def test_empty_wheelhouse_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            requirements = root / "requirements.txt"
            requirements.write_text("torch==2.13.0\n", encoding="utf-8")
            wheelhouse = root / "wheels"
            wheelhouse.mkdir()
            with self.assertRaisesRegex(ValueError, "no wheels"):
                build_manifest(requirements, wheelhouse)


if __name__ == "__main__":
    unittest.main()
