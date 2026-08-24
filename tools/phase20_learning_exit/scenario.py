"""Host orchestration for installed client and state-inspection processes."""

import json
import subprocess
import sys
from pathlib import Path


VERIFIED_OUTPUT = "PHASE20_VERIFIED_OUTPUT_NONCE"
UNVERIFIED_OUTPUT = "PHASE20_UNVERIFIED_OUTPUT_NONCE"
VERIFIED_PROMPT = f"Reply with exactly {VERIFIED_OUTPUT}"
UNVERIFIED_PROMPT = "PHASE20_UNVERIFIED_RAW_PROMPT_NONCE explain local operation"
REDACTION = "[terminal content removed after result retention]"


def run_client(installation, repository, service, mode: str) -> dict:
    output = service.run_root / f"client-{mode}.json"
    subprocess.run(
        (
            sys.executable,
            str(repository / "tools/phase20_learning_exit/client_process.py"),
            "--installed-python", str(installation.prefix / "active/python"),
            "--repository", str(repository),
            "--socket", str(service.runtime_root / "shell.sock"),
            "--mode", mode,
            "--output", str(output),
        ),
        check=True, capture_output=True, text=True, timeout=120,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def inspect_state(installation, repository: Path, product_root: Path, output: Path) -> dict:
    subprocess.run(
        (
            sys.executable,
            str(repository / "tools/phase20_learning_exit/inspect_process.py"),
            "--installed-python", str(installation.prefix / "active/python"),
            "--repository", str(repository),
            "--state-root", str(product_root / "state"),
            "--output", str(output),
        ),
        check=True, capture_output=True, text=True, timeout=120,
    )
    return json.loads(output.read_text(encoding="utf-8"))
