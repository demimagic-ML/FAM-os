"""Use only the installed Shell client contracts against the installed service."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


VERIFIED_PROMPT = "Reply with exactly PHASE20_VERIFIED_OUTPUT_NONCE"
UNVERIFIED_PROMPT = "PHASE20_UNVERIFIED_RAW_PROMPT_NONCE explain local operation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--mode", choices=("submit", "restart"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)
    from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
    from fam_os.shell import ShellAskCommand

    client = UnixShellCoreClient(UnixShellClientConfiguration(args.socket, 20))
    if args.mode == "submit":
        sessions = (
            client.ask(ShellAskCommand(
                "learning-verified", VERIFIED_PROMPT, verification_required=True,
            )).session_id,
            client.ask(ShellAskCommand(
                "learning-unverified", UNVERIFIED_PROMPT,
            )).session_id,
        )
    else:
        sessions = ("task-learning-verified", "task-learning-unverified")
    document = {"mode": args.mode, "results": tuple(
        _terminal(client, session_id) for session_id in sessions
    )}
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return 0


def _terminal(client, session_id: str) -> dict:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        snapshot = client.snapshot(session_id)
        if snapshot.result is not None:
            result = snapshot.result
            return {
                "session_id": session_id,
                "status": result.status.value,
                "assurance": result.assurance.value,
                "verified": result.verified,
                "content": result.content,
            }
        time.sleep(0.02)
    raise TimeoutError(f"installed task did not become terminal: {session_id}")


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
