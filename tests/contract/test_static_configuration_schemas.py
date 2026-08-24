import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from fam_os.schemas import STATIC_CONFIGURATION_SCHEMAS


class StaticConfigurationSchemaTests(unittest.TestCase):
    def test_every_strict_configuration_schema_is_tracked_and_valid(self) -> None:
        root = Path("schemas")
        self.assertEqual(len(STATIC_CONFIGURATION_SCHEMAS), len(set(STATIC_CONFIGURATION_SCHEMAS)))
        for relative in STATIC_CONFIGURATION_SCHEMAS:
            with self.subTest(schema=relative):
                path = root / relative
                self.assertTrue(path.is_file())
                Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
