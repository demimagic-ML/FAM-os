"""One restartable installed service session and content-free task probes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from fam_os.product.bundle_installation import SignedBundleInstallation

from tools.phase19_exit.console_client import ConsoleClient
from tools.phase23_hardware_matrix.telemetry import capture_profile_telemetry
from tools.phase23_installed_matrix.service import CandidateService


class InstalledSoakSession:
    def __init__(
        self, *, installation: SignedBundleInstallation,
        state_root: Path, run_root: Path,
        ollama_url: str, source_model_root: Path, manage_ollama: bool = True,
        launch_prefix: tuple[str, ...] = (),
    ) -> None:
        self.service = CandidateService(
            installation, state_root, run_root,
            ollama_url=ollama_url,
            source_model_root=source_model_root,
            manage_ollama=manage_ollama,
            validation_profile=(
                "full-reference-workstation" if manage_ollama else None
            ),
            launch_prefix=launch_prefix,
        )
        self.client: ConsoleClient | None = None

    @property
    def pid(self) -> int:
        value = self.service.pid
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeError("installed soak service is not running")
        return cast(int, value)

    @property
    def console(self) -> ConsoleClient:
        return self._client()

    def start(self) -> "InstalledSoakSession":
        self.service.start()
        token = (self.service.runtime_root / "console.token").read_text().strip()
        self.client = ConsoleClient(
            f"http://127.0.0.1:{self.service.port}", token,
        )
        return self

    def stop(self) -> None:
        self.service.stop()

    def crash(self) -> None:
        self.service.crash()

    def submit_ready(self, request_id: str) -> dict[str, Any]:
        document = self._client().create_verified(
            request_id, "Reply with exactly READY",
            {"kind": "exact_text", "expected_text": "READY"},
        )
        if not isinstance(document, dict) or any(
            not isinstance(key, str) for key in document
        ):
            raise RuntimeError("installed soak task returned an invalid document")
        return cast(dict[str, Any], document)

    def wait_ready_result(
        self, session_id: str, timeout: float = 360,
    ) -> dict[str, Any]:
        terminal = self._client().wait_for_terminal(session_id, timeout=timeout)
        result = terminal.get("result") or {}
        runs = self._client().verifications(session_id)
        passed = bool(
            result.get("status") == "verified"
            and result.get("content") == "READY"
            and runs
            and all(item.get("effective_trust") == "signed" for item in runs)
        )
        return {
            "session_id": session_id,
            "terminal_state": terminal.get("state"),
            "assurance": result.get("assurance"),
            "status": result.get("status"),
            "verification_run_count": len(runs),
            "selected_models": _selected_models(terminal, runs),
            "release_id": self.release_id(),
            "passed": passed,
        }

    def verified_ready(self, request_id: str) -> dict[str, Any]:
        accepted = self.submit_ready(request_id)
        session_id = accepted.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise RuntimeError("installed soak task omitted its session identity")
        return self.wait_ready_result(session_id)

    def resource_sample(self) -> dict[str, Any]:
        telemetry = capture_profile_telemetry(
            self.service, self._client().snapshot(),
        )
        provider_models = telemetry["provider_models"]
        nvidia = telemetry["host"]["nvidia"]
        return {
            "release_id": self.release_id(),
            "service_pid": self.pid,
            "memory_current": telemetry["systemd"].get("MemoryCurrent"),
            "memory_peak": telemetry["systemd"].get("MemoryPeak"),
            "swap_current": telemetry["systemd"].get("MemorySwapCurrent"),
            "provider_model_count": len(provider_models),
            "provider_models": tuple(
                str(item.get("model")) for item in provider_models
            ),
            "provider_vram_bytes": sum(
                int(item.get("size_vram_bytes") or 0)
                for item in provider_models
            ),
            "gpu_memory_used_mib": tuple(
                int(item.get("memory_used_mib") or 0) for item in nvidia
            ),
            "gpu_utilization_percent": tuple(
                int(item.get("utilization_percent") or 0) for item in nvidia
            ),
            "host_available_memory_bytes": telemetry["host"]["memory"].get(
                "MemAvailable"
            ),
            "filesystem_free_bytes": telemetry["host"][
                "state_filesystem"
            ].get("free_bytes"),
        }

    def release_id(self) -> str:
        manifest = json.loads((
            self.service.installation.prefix / "active/release-manifest.json"
        ).read_text("utf-8"))
        return str(manifest["payload"]["release_id"])

    def _client(self) -> ConsoleClient:
        if self.client is None:
            raise RuntimeError("installed soak session has not started")
        return self.client


class InstalledSoakSessionFactory:
    def __init__(
        self, installation: SignedBundleInstallation, work: Path,
        ollama_url: str, source_model_root: Path,
    ) -> None:
        self.installation = installation
        self.work = work
        self.ollama_url = ollama_url
        self.source_model_root = source_model_root
        self.state_root = work / "state"
        self._number = 0

    def new(self, label: str) -> InstalledSoakSession:
        self._number += 1
        return InstalledSoakSession(
            installation=self.installation,
            state_root=self.state_root,
            run_root=self.work / "runs" / f"{self._number:04d}-{label}",
            ollama_url=self.ollama_url,
            source_model_root=self.source_model_root,
            manage_ollama=True,
        )


def _selected_models(
    terminal: dict[str, Any], runs: list[dict[str, Any]],
) -> tuple[str, ...]:
    text = json.dumps((terminal, runs), sort_keys=True)
    known = (
        "qwen3:1.7b", "qwen2.5-coder:7b",
        "laguna-xs.2:q4_K_M", "gemma4:26b",
    )
    return tuple(model for model in known if model in text)
