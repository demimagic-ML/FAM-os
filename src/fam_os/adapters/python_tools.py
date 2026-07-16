"""Bounded temporary-file adapters for trusted Python analyzers."""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fam_os.verification.python.quality import AnalyzerResult, QualityGateStatus


@dataclass(frozen=True, slots=True)
class PythonToolAnalyzer:
    analyzer_id: str
    executable: Path
    arguments: tuple[str, ...]
    timeout_seconds: float = 10.0
    output_bytes: int = 16_384

    def analyze(self, source: str) -> AnalyzerResult:
        if not self.executable.is_file():
            return AnalyzerResult(self.analyzer_id, QualityGateStatus.ERROR, None, "analyzer unavailable")
        with tempfile.TemporaryDirectory(prefix="fam-python-analysis-") as directory:
            candidate = Path(directory) / "candidate.py"
            candidate.write_text(source, encoding="utf-8")
            try:
                result = subprocess.run(
                    (str(self.executable), *self.arguments, str(candidate)),
                    cwd=directory, capture_output=True, text=True,
                    timeout=self.timeout_seconds, env={"PATH": "/usr/bin:/bin"},
                )
            except (OSError, subprocess.SubprocessError) as error:
                return AnalyzerResult(self.analyzer_id, QualityGateStatus.ERROR, None, str(error))
        output = (result.stdout + result.stderr)[-self.output_bytes:]
        status = QualityGateStatus.PASSED if result.returncode == 0 else QualityGateStatus.FAILED
        return AnalyzerResult(self.analyzer_id, status, result.returncode, output)


def mypy_analyzer(venv: Path) -> PythonToolAnalyzer:
    return PythonToolAnalyzer("python.mypy-strict", venv / "bin/mypy", ("--strict", "--no-error-summary"))


def ruff_analyzer(venv: Path) -> PythonToolAnalyzer:
    return PythonToolAnalyzer("python.ruff", venv / "bin/ruff", ("check", "--output-format=concise"))
