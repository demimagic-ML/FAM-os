import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.phase23_hardware_matrix.contracts import HardwareMatrixSettings
from tools.phase23_hardware_matrix.evidence import finalize
from tools.phase23_hardware_matrix.owner_workload import OwnerModelQuiescence
from tools.phase23_hardware_matrix.profile_scenario import _profile_checks
from tools.phase23_hardware_matrix.scenario import run_hardware_matrix
from tools.phase23_hardware_matrix.telemetry import _parse_properties


class Phase23HardwareMatrixTests(unittest.TestCase):
    def test_settings_require_new_absolute_paths_and_safe_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            models = root / "models"
            repository.mkdir()
            models.mkdir()
            settings = HardwareMatrixSettings(
                repository, root / "output", "phase23-hardware-01", models,
            )
            self.assertEqual("phase23-hardware-01", settings.run_id)
            with self.assertRaisesRegex(ValueError, "identity"):
                HardwareMatrixSettings(
                    repository, root / "other", "unsafe/id", models,
                )

    def test_matrix_uses_short_private_execution_root_for_unix_sockets(self):
        with tempfile.TemporaryDirectory() as raw:
            settings = Mock()
            settings.output_root = Path(raw) / "output"
            with patch(
                "tools.phase23_hardware_matrix.scenario.tempfile.TemporaryDirectory",
                side_effect=RuntimeError("captured"),
            ) as temporary:
                with self.assertRaisesRegex(RuntimeError, "captured"):
                    run_hardware_matrix(settings)
            self.assertEqual("f23h-", temporary.call_args.kwargs["prefix"])

    def test_systemd_property_parser_preserves_environment_values(self):
        self.assertEqual(
            {
                "ActiveState": "active",
                "Environment": "CUDA_VISIBLE_DEVICES=-1 OLLAMA_HOST=127.0.0.1",
            },
            _parse_properties(
                "ActiveState=active\n"
                "Environment=CUDA_VISIBLE_DEVICES=-1 OLLAMA_HOST=127.0.0.1\n"
            ),
        )

    def test_profile_predicates_distinguish_cpu_and_full_hardware(self):
        compat = _telemetry(
            profile="compat-cpu-16gb", memory_max=str(16 * 1024**3),
            memory_high=str(14 * 1024**3), cpu_quota="23s", vram=0,
            environment=(
                "CUDA_VISIBLE_DEVICES=-1 GGML_VK_VISIBLE_DEVICES=-1 "
                "OLLAMA_LLM_LIBRARY=cpu_avx2"
            ),
        )
        full = _telemetry(
            profile="full-reference-workstation", memory_max="infinity",
            memory_high="infinity", cpu_quota="22s", vram=4 * 1024**3,
            environment="OLLAMA_HOST=127.0.0.1:11435",
        )

        self.assertTrue(_profile_checks("compat-cpu-16gb", compat)["passed"])
        self.assertTrue(
            _profile_checks("full-reference-workstation", full)["passed"],
        )

    def test_final_evidence_requires_both_profiles_strong_models_and_cleanup(self):
        document = {
            "profiles": {
                "compat-cpu-16gb": {"passed": True},
                "full-reference-workstation": {"passed": True},
            },
            "full_strong_escalation": {"passed": True},
            "owner_model_quiescence": {"passed": True},
            "complete_removal": True,
            "live_owner_service_preserved": True,
            "managed_service_inactive": True,
        }
        finalize(document)
        self.assertTrue(document["passed"])
        document["full_strong_escalation"] = {"passed": False}
        finalize(document)
        self.assertFalse(document["passed"])

    def test_owner_model_quiescence_is_explicit_and_rechecks_gpu(self):
        runtime = _FakeOwnerRuntime([
            _Loaded("laguna-xs.2:q4_K_M", 20, 12, 4096),
        ])
        with self.assertRaisesRegex(RuntimeError, "--quiesce-owner-models"):
            OwnerModelQuiescence(
                "http://127.0.0.1:11434", enabled=False, runtime=runtime,
            ).prepare()
        quiescence = OwnerModelQuiescence(
            "http://127.0.0.1:11434", enabled=True, runtime=runtime,
        )
        self.assertTrue(quiescence.prepare()["passed"])
        self.assertEqual(["laguna-xs.2:q4_K_M"], runtime.unloaded)
        self.assertTrue(quiescence.assert_idle()["passed"])

    def test_owner_monitor_evicts_gpu_model_that_returns_mid_scenario(self):
        runtime = _FakeOwnerRuntime([])
        quiescence = OwnerModelQuiescence(
            "http://127.0.0.1:11434", enabled=True, runtime=runtime,
            monitor_interval=0.01,
        )
        self.assertTrue(quiescence.prepare()["passed"])
        quiescence.start_monitor()
        runtime.loaded.append(_Loaded("nomic-embed-text", 2, 1, 2048))
        deadline = time.monotonic() + 1
        while runtime.loaded and time.monotonic() < deadline:
            time.sleep(0.01)

        final = quiescence.final()

        self.assertFalse(runtime.loaded)
        self.assertEqual(["nomic-embed-text"], final["monitor_evictions"])
        self.assertFalse(final["monitor_active"])
        self.assertTrue(final["passed"])


class _Loaded:
    def __init__(
        self, model_ref: str, resident_bytes: int,
        accelerator_bytes: int, context_tokens: int,
    ) -> None:
        self.model_ref = model_ref
        self.resident_bytes = resident_bytes
        self.accelerator_bytes = accelerator_bytes
        self.context_tokens = context_tokens


class _FakeOwnerRuntime:
    def __init__(self, loaded):
        self.loaded = list(loaded)
        self.unloaded = []

    def loaded_models(self):
        return tuple(self.loaded)

    def unload(self, model_ref):
        self.unloaded.append(model_ref)
        self.loaded = [item for item in self.loaded if item.model_ref != model_ref]


def _telemetry(
    *, profile: str, memory_max: str, memory_high: str, cpu_quota: str,
    vram: int, environment: str,
) -> dict:
    return {
        "systemd": {
            "ActiveState": "active", "MemorySwapMax": "0",
            "MemoryMax": memory_max, "MemoryHigh": memory_high,
            "CPUQuotaPerSecUSec": cpu_quota, "TasksMax": "512",
            "Environment": environment,
        },
        "cgroup": {"memory.events": "oom 0\noom_kill 0\n"},
        "provider_models": [{
            "model": "qwen3:1.7b", "size_vram_bytes": vram,
        }],
        "console": {
            "policy_description": f"profile.{profile}",
            "logical_cpus": "24",
            "schedulable_memory": "14.0 GiB",
            "schedulable_vram": f"{vram / 1024**3:.1f} GiB",
            "available_storage": "1000.0 GiB",
            "enabled_experts": "5",
            "signed_bindings": "5",
            "resident_models": "1",
            "resident_detail": "qwen3:1.7b",
        },
        "host": {
            "logical_cpu_count": 24,
            "memory": {
                "MemTotal": 64 * 1024**3,
                "MemAvailable": 40 * 1024**3,
            },
            "state_filesystem": {
                "total_bytes": 2 * 1024**4,
                "free_bytes": 1000 * 1024**3,
            },
            "nvidia": [{"name": "GPU", "memory_total_mib": 16 * 1024}],
        },
    }


if __name__ == "__main__":
    unittest.main()
