"""Submit and revisit installed Phase 20.7 control workloads."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from tools.phase20_control_exit.workload import OUTPUTS, PROMPTS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("seed", "adapted", "drift", "canary", "disabled", "restart"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)
    from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient

    client = UnixShellCoreClient(UnixShellClientConfiguration(args.socket, 30))
    if args.mode == "seed":
        results = tuple(_submit(client, index, True) for index in range(1, 6))
    elif args.mode == "adapted":
        results = (_submit(client, 6, True),)
    elif args.mode == "drift":
        results = (_submit(client, 7, True), _submit(client, 8, False))
    elif args.mode == "canary":
        results = (_submit(client, 9, False),)
    elif args.mode == "disabled":
        results = (_submit(client, 10, False),)
    else:
        results = tuple(
            _terminal(client, f"task-live-{index}") for index in range(1, 11)
        )
    args.output.write_text(
        json.dumps(
            {
                "mode": args.mode,
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return 0


def _submit(client, index: int, verified: bool) -> dict:
    from fam_os.shell import ShellAskCommand

    request_id = f"live-{index}"
    ask = ShellAskCommand(
        request_id,
        PROMPTS[index - 1],
        verification_required=verified,
    )
    if verified:
        from fam_os.schemas import dumps_document
        from fam_os.shell import ShellVerifiedAskCommand
        from fam_os.verification import (
            ExactTextVerification,
            VerificationDeclaration,
            contract_for_kind,
        )

        specification = ExactTextVerification(OUTPUTS[index - 1])
        declaration = VerificationDeclaration(
            f"declaration-{request_id}",
            request_id,
            contract_for_kind(specification.kind),
            specification,
        )
        accepted = client.ask_verified(
            ShellVerifiedAskCommand(
                ask,
                dumps_document(declaration),
            )
        )
    else:
        accepted = client.ask(ask)
    return _terminal(client, accepted.session_id)


def _terminal(client, session_id: str) -> dict:
    deadline = time.monotonic() + 30
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
        item
        for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
