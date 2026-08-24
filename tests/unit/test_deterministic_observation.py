import unittest
from types import SimpleNamespace

from fam_os.core.production.deterministic_observation import exact_directory_listing


class DeterministicObservationTests(unittest.TestCase):
    def test_directory_listing_preserves_exact_names_and_truncation(self):
        observation = SimpleNamespace(payload={
            "path": "/home/owner/project",
            "entries": [
                {"name": "src", "kind": "directory", "size_bytes": None},
                {"name": "a `literal` file.md", "kind": "file", "size_bytes": 12},
            ],
            "truncated": True,
        })

        result = exact_directory_listing(
            "List the top-level files and directories.", (observation,),
        )

        self.assertIn('Directories (1):\n- "src"', result)
        self.assertIn('Files (1):\n- "a `literal` file.md"', result)
        self.assertTrue(result.endswith("The bounded observation was truncated."))

    def test_analysis_prompt_still_uses_model_synthesis(self):
        observation = SimpleNamespace(payload={"entries": []})

        self.assertIsNone(exact_directory_listing(
            "Analyze what is in this folder and explain its architecture.",
            (observation,),
        ))

    def test_current_workspace_question_uses_model_synthesis(self):
        observation = SimpleNamespace(payload={
            "path": "/home/owner/Soccer_Oracle",
            "entries": [
                {"name": "GOALIE", "kind": "directory", "size_bytes": None},
                {"name": "AGENTS.md", "kind": "file", "size_bytes": 866},
            ],
        })

        self.assertIsNone(exact_directory_listing(
            "What's your current workspace?", (observation,),
        ))


if __name__ == "__main__":
    unittest.main()
