#!/usr/bin/env python3
"""Build the Phase 14.1 review disposition from immutable scanner evidence."""

from __future__ import annotations

import json
from pathlib import Path

from fam_os.security import FindingDisposition, build_review


ROOT = Path("artifacts/security/phase14.1")


def main() -> None:
    scanner_files = (
        ROOT / "bandit-after-remediation.json",
        ROOT / "python-dependencies-after-remediation.json",
        ROOT / "vscode-dependencies.json",
    )
    findings = (
        FindingDisposition(
            "GHSA-537c-gmf6-5ccf", "high", "fixed",
            "cryptography minimum raised to 48.0.1 and the dependency audit is clean",
        ),
        FindingDisposition(
            "B310", "medium", "fixed",
            "Ollama transport now permits only explicit HTTP and HTTPS schemes",
        ),
        FindingDisposition(
            "B108", "medium", "accepted",
            "findings are fixed destination names inside a new Bubblewrap mount namespace",
        ),
        FindingDisposition(
            "B603", "low", "accepted",
            "shell-free argv execution is the intended bounded adapter mechanism",
        ),
    )
    report = build_review("phase14.1-release-security", scanner_files, findings)
    output = ROOT / "security-review.json"
    output.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {output}; passed={report.passed}; blockers={len(report.release_blockers)}")


if __name__ == "__main__":
    main()
