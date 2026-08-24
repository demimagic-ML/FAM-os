import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fam_os.adapters.training.conversion_worker import _convert
from fam_os.adapters.training.isolated_conversion_command import (
    build_isolated_conversion_command,
)
from fam_os.expert_factory import ConversionOutputType, build_conversion_approval
from fam_os.product.factory_conversion_workspace import FactoryConversionWorkspace


NOW = datetime(2026, 7, 18, tzinfo=UTC)


class FactoryConversionIsolationTests(unittest.TestCase):
    def test_command_denies_network_and_applies_approved_limits(self) -> None:
        approval = _approval()
        command = build_isolated_conversion_command(
            approval=approval, environment=Path("/factory/environment"),
            worker_script=Path("/factory/conversion_worker.py"),
            llama_cpp=Path("/factory/llama.cpp"), model=Path("/factory/model"),
            adapter=Path("/factory/adapter"),
            input_directory=Path("/factory/input"),
            output_directory=Path("/factory/output"),
        )
        self.assertIn("--unshare-all", command)
        self.assertNotIn("--share-net", command)
        self.assertIn(f"MemoryMax={approval.maximum_ram_bytes}", command)
        self.assertIn(f"CPUQuota={approval.maximum_cpu_cores * 100}%", command)
        self.assertIn(f"RuntimeMaxSec={approval.maximum_wall_seconds}", command)
        self.assertFalse(any(value.startswith("LimitFSIZE=") for value in command))
        for name, value in (
            ("USER", "fam-conversion"),
            ("LOGNAME", "fam-conversion"),
            ("XDG_CACHE_HOME", "/tmp/cache"),
            ("HF_HOME", "/tmp/huggingface"),
            ("TORCH_HOME", "/tmp/torch"),
            ("TORCHINDUCTOR_CACHE_DIR", "/tmp/torchinductor"),
            ("TMPDIR", "/tmp"),
        ):
            index = command.index(name)
            self.assertEqual("--setenv", command[index - 1])
            self.assertEqual(value, command[index + 1])
        self.assertEqual(1, command.count("/model"))
        self.assertEqual(1, command.count("/adapter"))

    def test_workspace_is_private_and_config_is_approval_derived(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "conversions"
            prepared = FactoryConversionWorkspace(root, os.geteuid()).prepare(
                _approval(),
            )
            self.assertEqual(0o700, prepared.root.stat().st_mode & 0o777)
            self.assertEqual(0o600, prepared.config_path.stat().st_mode & 0o777)
            document = json.loads(prepared.config_path.read_text("utf-8"))
            self.assertEqual("bf16", document["base_output_type"])
            self.assertEqual("f16", document["adapter_output_type"])
            self.assertEqual(
                _approval().maximum_output_bytes,
                document["maximum_output_bytes"],
            )

    def test_worker_invokes_both_pinned_interfaces_and_hashes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.json"
            output = root / "output"
            output.mkdir()
            config.write_text(json.dumps({
                "adapter_output_type": "f16",
                "base_output_type": "bf16",
                "maximum_output_bytes": 1024 * 1024,
                "runtime_model_ref": "fam-code-specialist:canary",
            }))

            def fake_run(command: tuple[str, ...]) -> None:
                destination = Path(command[command.index("--outfile") + 1])
                destination.write_bytes(command[1].encode())

            with patch(
                "fam_os.adapters.training.conversion_worker._run",
                side_effect=fake_run,
            ) as runner:
                self.assertEqual(0, _convert(config, output))
            self.assertEqual(2, runner.call_count)
            result = json.loads((output / "worker-result.json").read_text())
            self.assertEqual("completed", result["status"])
            self.assertTrue((output / "base.gguf").is_file())
            self.assertTrue((output / "adapter.gguf").is_file())
            self.assertTrue((output / "Modelfile").is_file())


def _approval():
    return build_conversion_approval(
        approval_id="conversion-approval-1", evaluation_id="evaluation-1",
        comparison_decision_id="decision-1",
        comparison_decision_sha256="1" * 64, adapter_sha256="2" * 64,
        base_model_sha256="3" * 64, environment_sha256="4" * 64,
        base_output_type=ConversionOutputType.BF16,
        adapter_output_type=ConversionOutputType.F16,
        runtime_model_ref="fam-code-specialist:canary",
        maximum_output_bytes=8_000_000_000,
        maximum_wall_seconds=3600, maximum_ram_bytes=32 * 1024**3,
        maximum_cpu_cores=12, one_use_conversion_id="conversion-1",
        issued_at=NOW, expires_at=NOW + timedelta(hours=1),
    )


if __name__ == "__main__":
    unittest.main()
