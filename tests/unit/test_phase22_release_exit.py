import json
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.experts import parse_expert_capability_id
from tools.phase22_release_exit.scenario import (
    SPECIALIST_CAPABILITIES,
    _product_runtime_evidence,
)
from tools.phase22_release_exit.settings import SpecialistReleaseExitPaths
from tools.phase22_release_exit.suite import materialize_canary_suite


class Phase22ReleaseExitTests(unittest.TestCase):
    def test_specialist_declares_the_canonical_python_generation_capability(self) -> None:
        parsed = tuple(
            parse_expert_capability_id(value)
            for value in SPECIALIST_CAPABILITIES
        )

        self.assertEqual(("code.generate.python",), SPECIALIST_CAPABILITIES)
        self.assertEqual(("code",), tuple(value.domain for value in parsed))

    def test_release_evidence_identifies_the_executed_product_module(self) -> None:
        evidence = _product_runtime_evidence()

        self.assertTrue(Path(evidence["module_path"]).is_file())
        self.assertEqual(64, len(evidence["module_sha256"]))

    def test_canary_suite_binds_source_controlled_prompt_and_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompt = root / "prompt.json"
            tests = root / "tests.py"
            target = root / "private/suite.jsonl"
            prompt.write_text(json.dumps({"prompt": "Implement the function."}))
            tests.write_text("assert stable_topological_sort({}) == []\n")

            evidence = materialize_canary_suite(
                prompt_configuration=prompt, verifier_tests=tests, target=target,
            )

            document = json.loads(target.read_text())
            self.assertEqual("Implement the function.", document["prompt"])
            self.assertEqual(tests.read_text(), document["test_source"])
            self.assertEqual(1, evidence["case_count"])
            self.assertEqual(0o600, target.stat().st_mode & 0o777)

    def test_release_paths_require_absolute_safe_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).absolute()
            directories = tuple(root / name for name in ("run", "env", "llama", "model"))
            for directory in directories:
                directory.mkdir()
            files = tuple(
                root / name for name in ("manifest.json", "prompt.json", "tests.py", "ollama")
            )
            for path in files:
                path.write_text("fixture")
            os.chmod(files[-1], 0o700)

            paths = SpecialistReleaseExitPaths(
                directories[0], directories[1], files[0], directories[2],
                directories[3], files[1], files[2], files[3],
            )

            self.assertEqual(directories[0], paths.state_root)
            self.assertEqual(
                directories[0] / "state/fam.sqlite3",
                paths.state_root / "state/fam.sqlite3",
            )
            self.assertEqual(
                directories[0] / "release-attempt-02",
                paths.release_root("attempt-02"),
            )


if __name__ == "__main__":
    unittest.main()
