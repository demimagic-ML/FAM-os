"""Bounded real-toolchain verifiers for JavaScript, TypeScript, and Rust."""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fam_os.verification.language_quality import (
    LanguageGateEvidence,
    LanguageGateStatus,
    LanguageQualityReport,
)


@dataclass(frozen=True, slots=True)
class ToolGate:
    gate_id: str
    command: tuple[str, ...]
    executes_candidate: bool = False


@dataclass(frozen=True, slots=True)
class TemporaryToolchainVerifier:
    language_id: str
    extension: str
    toolchain_version: str
    gates: tuple[ToolGate, ...]
    timeout_seconds: float = 15.0
    output_bytes: int = 16_384
    trusted_fixture_execution: bool = False

    def verify(self, verification_id: str, source: str) -> LanguageQualityReport:
        with tempfile.TemporaryDirectory(prefix=f"fam-{self.language_id}-") as directory:
            candidate = Path(directory) / f"candidate.{self.extension}"
            candidate.write_text(source, encoding="utf-8")
            evidence = tuple(self._run(gate, candidate, Path(directory)) for gate in self.gates)
        return LanguageQualityReport(
            verification_id, self.language_id, self.toolchain_version, evidence,
        )

    def _run(self, gate: ToolGate, candidate: Path, cwd: Path) -> LanguageGateEvidence:
        if gate.executes_candidate and not self.trusted_fixture_execution:
            return LanguageGateEvidence(
                gate.gate_id, LanguageGateStatus.ERROR, None,
                "candidate execution requires an activated isolation provider",
            )
        command = tuple(
            value.replace("{candidate}", str(candidate)).replace("{cwd}", str(cwd))
            for value in gate.command
        )
        try:
            result = subprocess.run(
                command, cwd=cwd, capture_output=True, text=True,
                timeout=self.timeout_seconds, env={"PATH": "/usr/bin:/bin"},
            )
        except (OSError, subprocess.SubprocessError) as error:
            return LanguageGateEvidence(gate.gate_id, LanguageGateStatus.ERROR, None, str(error))
        output = (result.stdout + result.stderr)[-self.output_bytes:]
        status = LanguageGateStatus.PASSED if result.returncode == 0 else LanguageGateStatus.FAILED
        return LanguageGateEvidence(gate.gate_id, status, result.returncode, output)
