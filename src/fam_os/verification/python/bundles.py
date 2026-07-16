"""Trusted Python acceptance-test bundles."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TrustedPythonTests:
    bundle_id: str
    source: str

    def __post_init__(self) -> None:
        if not self.bundle_id.strip():
            raise ValueError("bundle_id must not be empty")
        if not self.source.strip():
            raise ValueError("trusted test source must not be empty")
        ast.parse(self.source)


def load_trusted_python_tests(path: Path, bundle_id: str) -> TrustedPythonTests:
    return TrustedPythonTests(bundle_id, path.read_text(encoding="utf-8"))
