"""Run installed FAM_OS with deterministic scripted terminal outcomes."""

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
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    _installed_imports(args.installed_python, args.repository)
    from fam_os.product.service import LocalProductService, ProductServiceSettings

    runtime = _Runtime(args.responses)
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
    return 0


class _Runtime:
    def __init__(self, responses: Path) -> None:
        self._responses = list(json.loads(responses.read_text(encoding="utf-8")))

    def chat(self, _request):
        if not self._responses:
            raise RuntimeError("Phase 20.5 restart attempted unexpected inference")
        return type("Response", (), {"content": self._responses.pop(0)})()

    def loaded_models(self):
        return ()

    def unload(self, _model_ref):
        return None

    def prewarm(self, _model_ref, keep_alive="10m"):
        return None


def _installed_imports(installed_python: Path, repository: Path) -> None:
    root = repository.resolve()
    sys.path[:] = [str(installed_python.resolve())] + [
        item for item in sys.path
        if item and not Path(item).resolve().is_relative_to(root)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
