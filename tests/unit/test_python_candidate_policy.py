import unittest

from fam_os.verification.python import (
    extract_python_candidate,
    sanitize_python_candidate,
)


GOOD_FENCE = """```python
def answer(value):
    return value + 1
```"""


class PythonCandidatePolicyTests(unittest.TestCase):
    def test_extracts_fenced_python(self) -> None:
        self.assertIn("def answer", extract_python_candidate(GOOD_FENCE))

    def test_rejects_forbidden_import(self) -> None:
        with self.assertRaisesRegex(ValueError, "import is not allowed"):
            sanitize_python_candidate("import os\ndef run():\n    return 1\n")

    def test_removes_top_level_example(self) -> None:
        sanitized = sanitize_python_candidate("def run():\n    return 1\nprint(run())\n")
        self.assertNotIn("print", sanitized)

    def test_selects_first_syntactically_valid_fence(self) -> None:
        content = "```python\ndef broken(:\n```\n```py\ndef valid():\n    return 1\n```"
        self.assertIn("def valid", extract_python_candidate(content))

    def test_rejects_builtins_mapping_bypass(self) -> None:
        code = "def run():\n    return __builtins__['eval']('1 + 1')\n"
        with self.assertRaisesRegex(ValueError, "__builtins__"):
            sanitize_python_candidate(code)

    def test_rejects_dynamic_dunder_access(self) -> None:
        code = "def run(value):\n    return getattr(value, '__class__')\n"
        with self.assertRaisesRegex(ValueError, "getattr"):
            sanitize_python_candidate(code)

    def test_rejects_nested_decorators(self) -> None:
        code = "def outer():\n    @property\n    def inner():\n        return 1\n    return inner\n"
        with self.assertRaisesRegex(ValueError, "decorators"):
            sanitize_python_candidate(code)


if __name__ == "__main__":
    unittest.main()
