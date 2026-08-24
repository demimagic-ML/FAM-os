import unittest
from pathlib import Path

from fam_os.adapters.bubblewrap import BubblewrapSandboxRunner
from fam_os.product.canary_verifier import DeclaredCanaryVerifier
from fam_os.product.composition.verifier_unit import production_verifier_catalog


class DeclaredCanaryVerifierTests(unittest.TestCase):
    def test_uses_exact_activated_production_verifier_package(self) -> None:
        tests = Path(
            "tests/fixtures/verification/stable_topological_sort_tests.py",
        ).read_text("utf-8")
        candidate = """
def stable_topological_sort(graph):
    order = list(graph)
    for name in graph:
        for neighbor in graph[name]:
            if neighbor not in order:
                order.append(neighbor)
    indegree = {name: 0 for name in order}
    outgoing = {name: [] for name in order}
    for name in order:
        for neighbor in graph.get(name, []):
            indegree[neighbor] += 1
            outgoing[name].append(neighbor)
    result = []
    while len(result) < len(order):
        current = None
        for name in order:
            if indegree[name] == 0 and name not in result:
                current = name
                break
        if current is None:
            raise ValueError("cycle")
        result.append(current)
        for neighbor in outgoing[current]:
            indegree[neighbor] -= 1
    return result
"""
        verifier = DeclaredCanaryVerifier(
            production_verifier_catalog(), BubblewrapSandboxRunner(),
        )
        self.assertTrue(verifier.verify(
            verifier_id="python.deterministic-tests.v1",
            case_id="stable-toposort", candidate=candidate,
            bundle_id="stable-toposort-v2", test_source=tests,
        ))
        self.assertFalse(verifier.verify(
            verifier_id="verifier.python.unknown", case_id="unknown",
            candidate=candidate, bundle_id="stable-toposort-v2",
            test_source=tests,
        ))


if __name__ == "__main__":
    unittest.main()
