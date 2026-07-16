"""Opt-in live parity test for the migrated deterministic Python verifier."""

import os
import unittest
from pathlib import Path

from fam_os.adapters.bubblewrap import BubblewrapSandboxRunner
from fam_os.verification import VerificationRequest, VerificationStatus
from fam_os.verification.python import PythonVerifier, load_trusted_python_tests
from rnf.verifier import verify_python as parent_verify_python


TESTS_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "verification"
    / "stable_topological_sort_parity_tests.py"
)

GOOD_CODE = '''```python
def stable_topological_sort(graph):
    nodes = list(graph)
    for neighbors in graph.values():
        for node in neighbors:
            if node not in nodes:
                nodes.append(node)
    indegree = {node: 0 for node in nodes}
    for neighbors in graph.values():
        for node in neighbors:
            indegree[node] += 1
    ready = [node for node in nodes if indegree[node] == 0]
    result = []
    while ready:
        node = ready.pop(0)
        result.append(node)
        for neighbor in graph.get(node, []):
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                ready.append(neighbor)
    if len(result) != len(nodes):
        raise ValueError("cycle")
    return result
```'''


@unittest.skipUnless(os.getenv("FAM_VERIFIER_PARITY") == "1", "live parity disabled")
class PythonVerifierParityTests(unittest.TestCase):
    def setUp(self) -> None:
        tests = load_trusted_python_tests(TESTS_PATH, "stable-toposort.v1")
        self.verifier = PythonVerifier(BubblewrapSandboxRunner(), tests)

    def test_accepts_same_correct_implementation(self) -> None:
        parent = parent_verify_python(GOOD_CODE, TESTS_PATH)
        migrated = self.verifier.verify(VerificationRequest("parity-good", GOOD_CODE))
        self.assertTrue(parent.passed, parent.stderr)
        self.assertEqual(migrated.status, VerificationStatus.PASSED)
        self.assertEqual(migrated.evidence.isolation, "bubblewrap")

    def test_rejects_same_unstable_implementation(self) -> None:
        content = GOOD_CODE.replace("ready.append(neighbor)", "ready.insert(0, neighbor)")
        parent = parent_verify_python(content, TESTS_PATH)
        migrated = self.verifier.verify(VerificationRequest("parity-unstable", content))
        self.assertFalse(parent.passed)
        self.assertEqual(migrated.status, VerificationStatus.FAILED)
        self.assertIn("stable branch order", migrated.failure_details())


if __name__ == "__main__":
    unittest.main()
