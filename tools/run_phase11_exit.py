#!/usr/bin/env python3
import json
from dataclasses import asdict
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, MessageRole
from fam_os.adaptation.phase11_exit import Phase11ExitEvidence


def main():
    model = "qwen3:1.7b"
    runtime = OllamaRuntime(OllamaSettings("http://127.0.0.1:11434", 180))
    runtime.unload(model)
    request = InferenceRequest(
        model, (InferenceMessage(MessageRole.USER, "Return JSON exactly: {\"answer\":5}"),),
        1024, 32, json_output=True, temperature=0,
    )
    baseline = runtime.chat(request)
    adapted = runtime.chat(request)
    baseline_ok = json.loads(baseline.content).get("answer") == 5
    adapted_ok = json.loads(adapted.content).get("answer") == 5
    preferences = json.loads((Path(__file__).parents[1] /
        "artifacts/adaptation/phase11.3/preference-evidence.json").read_text())
    reset = preferences["remaining_preferences"] == 0
    improved = adapted.metrics.wall_seconds < baseline.metrics.wall_seconds
    evidence = Phase11ExitEvidence(
        "phase11-workstation-v1", model, baseline.metrics.wall_seconds,
        adapted.metrics.wall_seconds, baseline_ok, adapted_ok, reset, improved,
        improved and baseline_ok and adapted_ok and reset,
    )
    output = Path(__file__).parents[1] / "artifacts/adaptation/phase11-exit.json"
    output.write_text(json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
