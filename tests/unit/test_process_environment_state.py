import json
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.integration.process_state import ProcessEnvironmentState


class ProcessEnvironmentStateTests(unittest.TestCase):
    def test_legacy_state_normalizes_without_inventing_secret_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = ProcessEnvironmentState(root, "legacy")
            state.claim()
            path = root / ".fam/integration/process-legacy.json"
            value = json.loads(path.read_text())
            value.pop("secret_roots")
            path.write_text(json.dumps(value))

            self.assertEqual([], state.load()["secret_roots"])

    def test_secret_root_is_durable_before_unit_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = ProcessEnvironmentState(root, "current")
            state.claim()
            state.record_secret_root(".fam/secret-injection/process-abc")

            value = state.load()
            self.assertEqual([], value["units"])
            self.assertEqual(
                [".fam/secret-injection/process-abc"], value["secret_roots"],
            )


if __name__ == "__main__":
    unittest.main()
