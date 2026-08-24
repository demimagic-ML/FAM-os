"""Exercise the production escalation chain plus both installed strong experts."""

from __future__ import annotations

from pathlib import Path

from tools.phase19_exit.console_client import ConsoleClient
from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings

from .model_control import restrict_candidate_experts
from .service import CandidateService


STRONG_MODELS = ("laguna-xs.2:q4_K_M", "gemma4:26b")


def run_escalation_scenario(
    *, installation, repository: Path, root: Path, ollama_url: str,
    source_model_root: Path, manage_ollama: bool = False,
    validation_profile: str | None = None,
) -> dict[str, object]:
    runtime = None if manage_ollama else OllamaRuntime(OllamaSettings(ollama_url, 30))
    resident_before = () if runtime is None else _strong_resident(runtime)
    if resident_before:
        raise RuntimeError(
            "strong qualification requires initially nonresident strong models: "
            + ", ".join(resident_before)
        )
    prompt = _prompt(repository)
    tests = (repository / "tests/fixtures/verification/stable_topological_sort_tests.py").read_text()
    verification = {
        "kind": "python_tests", "bundle_id": "stable-toposort-v2",
        "test_source": tests,
    }
    chain_service = CandidateService(
        installation, root / "chain-state", root / "chain-run",
        ollama_url=ollama_url, source_model_root=source_model_root,
        manage_ollama=manage_ollama,
        validation_profile=validation_profile,
    )
    cleanup = []
    chain_provider_models = ()
    try:
        with chain_service:
            chain = _task(
                chain_service, "phase23-escalation-chain", prompt, verification,
            )
            chain_provider = runtime or OllamaRuntime(
                OllamaSettings(ollama_url, 30),
            )
            chain_provider_models = _known_provider_models(chain_provider)
    finally:
        cleanup.append({
            "after": "chain",
            "unloaded": () if runtime is None else _clear_strong(runtime),
            "managed_provider_stopped": manage_ollama,
        })
    probes = []
    for index, model_ref in enumerate(STRONG_MODELS):
        state = root / f"strong-state-{index}"
        seed = CandidateService(
            installation, state, root / f"strong-seed-run-{index}",
            ollama_url=ollama_url, source_model_root=source_model_root,
            manage_ollama=manage_ollama,
            validation_profile=validation_profile,
        )
        with seed:
            pass
        control = restrict_candidate_experts(
            installation, repository, state, root / f"strong-control-{index}.json",
            model_ref,
        )
        service = CandidateService(
            installation, state, root / f"strong-run-{index}",
            ollama_url=ollama_url, source_model_root=source_model_root,
            model_ref=model_ref,
            manage_ollama=manage_ollama,
            validation_profile=validation_profile,
        )
        try:
            with service:
                probe = _task(service, f"phase23-strong-{index}", prompt, verification)
        finally:
            cleanup.append({
                "after": model_ref,
                "unloaded": () if runtime is None else _clear_strong(runtime),
                "managed_provider_stopped": manage_ollama,
            })
        probe["expert_control"] = control
        probes.append(probe)
    chain_models = tuple(dict.fromkeys((
        *_models(chain), *chain_provider_models,
    )))
    probe_models = tuple(_selected_model(item) for item in probes)
    return {
        "chain": chain, "chain_models": chain_models,
        "chain_provider_models": chain_provider_models,
        "strong_probes": probes, "strong_probe_models": probe_models,
        "strong_resident_before": resident_before,
        "strong_cleanup": cleanup,
        "strong_resident_after": (
            () if runtime is None else _strong_resident(runtime)
        ),
        "managed_provider": manage_ollama,
        "passed": all((
            chain["passed"], any(model in STRONG_MODELS for model in chain_models),
            probe_models == STRONG_MODELS,
            all(item["passed"] for item in probes),
            runtime is None or not _strong_resident(runtime),
        )),
    }


def _task(service, request_id, prompt, verification):
    client = _client(service)
    accepted = client.create_verified(request_id, prompt, verification)
    terminal = client.wait_for_terminal(accepted["session_id"], timeout=900)
    runs = client.verifications(accepted["session_id"])
    budget = client.attempt_budget(accepted["session_id"])
    result = terminal.get("result") or {}
    return {
        "accepted": accepted, "terminal": terminal,
        "verification_runs": runs, "attempt_budget": budget,
        "passed": result.get("status") == "verified" and bool(runs),
    }


def _models(task: dict) -> tuple[str, ...]:
    values = []
    for value in (task["accepted"], task["terminal"], task["verification_runs"]):
        text = str(value)
        for model in ("qwen2.5-coder:7b", *STRONG_MODELS):
            if model in text and model not in values:
                values.append(model)
    return tuple(values)


def _selected_model(task: dict) -> str:
    models = tuple(model for model in STRONG_MODELS if model in _models(task))
    return models[0] if len(models) == 1 else ""


def _prompt(repository: Path) -> str:
    import json

    document = json.loads((
        repository / "configs/benchmarks/full-workstation-verified-smoke-gemma4-26b.json"
    ).read_text())
    return document["prompt"]


def _client(service) -> ConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return ConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _strong_resident(runtime) -> tuple[str, ...]:
    loaded = {item.model_ref for item in runtime.loaded_models()}
    return tuple(model for model in STRONG_MODELS if model in loaded)


def _known_provider_models(runtime) -> tuple[str, ...]:
    loaded = {item.model_ref for item in runtime.loaded_models()}
    return tuple(
        model for model in ("qwen2.5-coder:7b", *STRONG_MODELS)
        if model in loaded
    )


def _clear_strong(runtime) -> tuple[str, ...]:
    unloaded = []
    for model_ref in _strong_resident(runtime):
        runtime.unload(model_ref)
        unloaded.append(model_ref)
    remaining = _strong_resident(runtime)
    if remaining:
        raise RuntimeError(
            "strong qualification could not confirm model unload: "
            + ", ".join(remaining)
        )
    return tuple(unloaded)
