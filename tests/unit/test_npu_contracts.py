import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fam_os.scheduler import (
    NpuHardwareEvidence,
    NpuInvestigationOutcome,
    NpuInvestigationReport,
    NpuMicroExpertEvidence,
    NpuRuntimeEvidence,
)


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def report() -> NpuInvestigationReport:
    hardware = NpuHardwareEvidence(
        "0x8086", "0xad1d", "Arrow Lake NPU", "intel_vpu", "1.0.0",
        "ubuntu 24.04", "6.17.0", True, False, True, "delegated-device-group",
    )
    runtime = NpuRuntimeEvidence(
        "OpenVINO", "2026.2", "1.33", "1.27", ("CPU", "NPU"),
        "Intel AI Boost", "NPU", ("NPU",), False, True,
    )
    expert = NpuMicroExpertEvidence(
        "expert.route.npu", "route.intent.linear.v1", "openvino-ir",
        "a" * 64, "b" * 64, "c" * 64, "code", "code",
        ("code", "retrieval", "math", "general"), (0.97, 0.01, 0.01, 0.01),
        10.0, 2.0, (1.0, 0.9, 0.8), False,
    )
    return NpuInvestigationReport(
        "report", NOW, NOW + timedelta(seconds=1), "full-reference-workstation",
        NpuInvestigationOutcome.SUPPORTED, hardware, runtime, expert, None,
    )


class NpuContractTests(unittest.TestCase):
    def test_supported_report_requires_npu_only_execution(self):
        value = report()
        with self.assertRaisesRegex(ValueError, "NPU-only"):
            replace(value, runtime=replace(value.runtime, execution_devices=("CPU",)))

    def test_fallback_cannot_be_reported_as_npu_evidence(self):
        value = report()
        with self.assertRaisesRegex(ValueError, "fallback"):
            replace(value.micro_expert, fallback_used=True)

    def test_wrong_classification_is_rejected(self):
        value = report()
        with self.assertRaisesRegex(ValueError, "classification failed"):
            replace(value.micro_expert, observed_label="retrieval")

    def test_unsupported_report_names_blocking_gate(self):
        value = report()
        unsupported = replace(
            value, outcome=NpuInvestigationOutcome.UNSUPPORTED,
            micro_expert=None, blocking_gate="runtime.npu_unavailable",
        )
        self.assertEqual(unsupported.blocking_gate, "runtime.npu_unavailable")


if __name__ == "__main__":
    unittest.main()
