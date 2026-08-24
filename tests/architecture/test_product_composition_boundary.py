import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
COMPOSITION_ROOTS = (
    ROOT / "src/fam_os/product/service.py",
    ROOT / "src/fam_os/product/cli.py",
)
FORBIDDEN_IMPORTS = (
    "fam_os.application_acceptance",
    "fam_os.product.phase14_exit",
    "fam_os.product.phase15_exit",
    "tests",
    "tools",
)


class ProductCompositionBoundaryTests(unittest.TestCase):
    def test_production_roots_cannot_import_acceptance_or_evidence_builders(self) -> None:
        violations = []
        for path in COMPOSITION_ROOTS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                for imported in _imports(node):
                    if imported.startswith(FORBIDDEN_IMPORTS):
                        violations.append(f"{path.name}:{node.lineno}:{imported}")
        self.assertEqual([], violations)

    def test_every_auxiliary_model_consumer_uses_residency_facade(self) -> None:
        path = ROOT / "src/fam_os/product/service.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        calls = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                calls.setdefault(_expression_name(node.func), []).append(node)

        live = _only(calls, "ProductLiveAdaptation")
        self.assertEqual("self.model_residency", _expression_name(live.args[2]))
        self.assertEqual("self.model_residency", _expression_name(live.args[3]))

        remote = _only(calls, "ProductRemoteExecutionServer")
        self.assertEqual("self.model_residency", _expression_name(remote.args[0]))
        self.assertEqual("self.model_residency", _expression_name(remote.args[2]))

        factory = _only(calls, "ProductFactoryControl")
        self.assertEqual("self.model_residency", _expression_name(factory.args[4]))
        self.assertEqual("self.model_residency", _expression_name(factory.args[5]))

        release = _only(calls, "compose_factory_release")
        self.assertEqual(
            "self.model_residency",
            _expression_name(_keyword(release, "runtime")),
        )

        for name in (
            "document_memory.compose_document_index_service",
            "document_memory.compose_grounded_retrieval",
        ):
            document = _only(calls, name)
            self.assertEqual(
                "self.model_residency", _expression_name(document.args[1]),
            )
            self.assertEqual(
                "self.model_residency", _expression_name(document.args[2]),
            )

        gateway = _only(calls, "ProductionTaskGateway")
        self.assertEqual(
            "self.model_residency",
            _expression_name(_keyword(gateway, "residency")),
        )


def _imports(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


def _expression_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _expression_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _only(calls: dict[str, list[ast.Call]], name: str) -> ast.Call:
    matches = calls.get(name, [])
    if len(matches) != 1:
        raise AssertionError(f"expected one {name} composition, found {len(matches)}")
    return matches[0]


def _keyword(call: ast.Call, name: str) -> ast.AST:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    raise AssertionError(f"missing {name} keyword")


if __name__ == "__main__":
    unittest.main()
