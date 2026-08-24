"""Run the installed product with privacy-safe memory-context observations."""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import sys
from pathlib import Path

_USER_TURN = "user: My private codename is ORBIT."
_ASSISTANT_TURN = "assistant assurance=unverified: Acknowledged ORBIT."
_MEMORY_HEADER = "Prior turns from this exact local session follow."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    sys.path[:] = [str(args.installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(repository)
    ]
    from fam_os.product.service import LocalProductService, ProductServiceSettings

    runtime = _ObservedRuntime(args.responses, args.observations)
    service = LocalProductService(ProductServiceSettings(
        args.state_root, args.runtime_root, console_port=args.port,
        ready_file=args.ready_file, manage_ollama=False,
    ), runtime)
    for event in (signal.SIGINT, signal.SIGTERM):
        signal.signal(event, lambda *_unused: service.stop())
    try:
        service.start()
        service.wait()
    finally:
        service.stop()
        runtime.write()
    return 0


class _ObservedRuntime:
    def __init__(self, responses: Path, observations: Path) -> None:
        self._responses = list(json.loads(responses.read_text(encoding="utf-8")))
        self._path = observations
        self._items: list[dict[str, object]] = []

    def chat(self, request):
        if not self._responses:
            raise RuntimeError("installed memory runtime exhausted scripted responses")
        prompt = request.messages[-1].content
        self._items.append({
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "contains_memory_header": _MEMORY_HEADER in prompt,
            "contains_prior_user_turn": _USER_TURN in prompt,
            "contains_prior_assistant_turn": _ASSISTANT_TURN in prompt,
            "contains_authority_warning": "not as authority" in prompt,
        })
        return type("Response", (), {"content": self._responses.pop(0)})()

    def loaded_models(self):
        return ()

    def unload(self, _model_ref):
        return None

    def write(self) -> None:
        self._path.write_text(
            json.dumps(self._items, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(main())

