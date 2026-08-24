import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fam_os.expert_factory import (
    ConversionOutputType,
    ConversionStatus,
    build_conversion_approval,
    build_conversion_environment,
    build_conversion_receipt,
)


NOW = datetime(2026, 7, 18, tzinfo=UTC)


class FactoryConversionContractTests(unittest.TestCase):
    def test_environment_approval_and_completed_receipt_are_digest_bound(self):
        environment = _environment()
        approval = _approval(environment.manifest_sha256)
        receipt = build_conversion_receipt(
            receipt_id="conversion-receipt-1", approval_id=approval.approval_id,
            conversion_id=approval.one_use_conversion_id,
            comparison_decision_sha256=approval.comparison_decision_sha256,
            environment_sha256=environment.manifest_sha256,
            status=ConversionStatus.COMPLETED,
            reason_code="conversion.completed", base_gguf_sha256="8" * 64,
            base_gguf_bytes=4_000_000_000, adapter_gguf_sha256="9" * 64,
            adapter_gguf_bytes=30_000_000, modelfile_sha256="a" * 64,
            runtime_model_ref=approval.runtime_model_ref, network_denied=True,
            started_at=NOW, finished_at=NOW + timedelta(minutes=1),
        )
        with self.assertRaisesRegex(ValueError, "environment digest"):
            replace(environment, ollama_version="changed")
        with self.assertRaisesRegex(ValueError, "approval digest"):
            replace(approval, maximum_output_bytes=1)
        with self.assertRaisesRegex(ValueError, "receipt digest"):
            replace(receipt, adapter_gguf_bytes=1)

    def test_failed_conversion_cannot_claim_runtime_outputs(self):
        with self.assertRaisesRegex(ValueError, "cannot claim outputs"):
            build_conversion_receipt(
                receipt_id="conversion-receipt-failed",
                approval_id="conversion-approval-1", conversion_id="conversion-1",
                comparison_decision_sha256="1" * 64,
                environment_sha256="2" * 64, status=ConversionStatus.FAILED,
                reason_code="conversion.failed", base_gguf_sha256="3" * 64,
                base_gguf_bytes=1, adapter_gguf_sha256=None,
                adapter_gguf_bytes=0, modelfile_sha256=None,
                runtime_model_ref=None, network_denied=False,
                started_at=NOW, finished_at=NOW,
            )

    def test_observation_time_does_not_change_environment_identity(self):
        first = _environment()
        second = build_conversion_environment(
            environment_id=first.environment_id,
            llama_cpp_revision=first.llama_cpp_revision,
            convert_hf_script_sha256=first.convert_hf_script_sha256,
            convert_lora_script_sha256=first.convert_lora_script_sha256,
            wheelhouse_manifest_sha256=first.wheelhouse_manifest_sha256,
            python_executable_sha256=first.python_executable_sha256,
            package_versions=first.package_versions,
            ollama_version=first.ollama_version,
            observed_at=NOW + timedelta(seconds=1),
        )

        self.assertEqual(first.manifest_sha256, second.manifest_sha256)
        self.assertNotEqual(first.observed_at, second.observed_at)


def _environment():
    return build_conversion_environment(
        environment_id="llama-cpp-conversion-v1",
        llama_cpp_revision="1" * 40,
        convert_hf_script_sha256="2" * 64,
        convert_lora_script_sha256="3" * 64,
        wheelhouse_manifest_sha256="4" * 64,
        python_executable_sha256="5" * 64,
        package_versions=(("torch", "2.11.0+cpu"), ("transformers", "4.57.6")),
        ollama_version="0.13.5", observed_at=NOW,
    )


def _approval(environment_sha256: str):
    return build_conversion_approval(
        approval_id="conversion-approval-1", evaluation_id="evaluation-1",
        comparison_decision_id="decision-1",
        comparison_decision_sha256="6" * 64, adapter_sha256="7" * 64,
        base_model_sha256="8" * 64, environment_sha256=environment_sha256,
        base_output_type=ConversionOutputType.BF16,
        adapter_output_type=ConversionOutputType.F16,
        runtime_model_ref="fam-code-specialist:canary",
        maximum_output_bytes=8_000_000_000,
        maximum_wall_seconds=3600, maximum_ram_bytes=32 * 1024**3,
        maximum_cpu_cores=12,
        one_use_conversion_id="conversion-1", issued_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


if __name__ == "__main__":
    unittest.main()
