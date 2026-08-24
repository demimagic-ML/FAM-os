import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
TARGET = ROOT / "src/fam_os/product/composition/core_storage.py"


class ProductionCoreStorageBoundaryTests(unittest.TestCase):
    def test_composition_has_no_in_memory_registry_dependency(self) -> None:
        source = TARGET.read_text(encoding="utf-8")
        self.assertNotIn("InMemory", source)
        tree = ast.parse(source, filename=str(TARGET))
        imports = [
            node.module or "" for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        self.assertFalse(any(name.endswith("_registry") for name in imports))


if __name__ == "__main__":
    unittest.main()
