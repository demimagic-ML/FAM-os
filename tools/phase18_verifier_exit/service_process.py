"""Run the installed product with a deterministic candidate source for qualification."""

from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path


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

    runtime = _ScriptedRuntime(args.responses, args.observations)
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
        runtime.write_observations()
    return 0


class _ScriptedRuntime:
    def __init__(self, responses: Path, observations: Path) -> None:
        self._responses = list(json.loads(responses.read_text(encoding="utf-8")))
        self._observations_path = observations
        self._observations: list[dict[str, object]] = []

    def chat(self, request):
        if not self._responses:
            raise RuntimeError("installed verifier runtime exhausted scripted candidates")
        self._observations.append({
            "model_ref": request.model_ref,
            "json_output": request.json_output,
            "image_count": sum(len(message.images) for message in request.messages),
            "prompt_sha256": _digest(request.messages[-1].content),
        })
        return type("Response", (), {"content": self._responses.pop(0)})()

    def loaded_models(self):
        return ()

    def unload(self, _model_ref):
        return None

    def write_observations(self) -> None:
        self._observations_path.write_text(
            json.dumps(self._observations, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _digest(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
