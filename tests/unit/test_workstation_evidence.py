import unittest

from fam_os.adapters.linux.nvidia import NvidiaResourceReading
from fam_os.adapters.linux.block_io import BlockIoReading
from fam_os.core.ports.inference import LoadedModel
from fam_os.supervisor import ResourceSnapshot
from tools.workstation.evidence import EvidencePoint, _evidence_payload


def point(
    cpu: int,
    read_bytes: int,
    gpu_bytes: int,
    models: tuple[LoadedModel, ...] = (),
) -> EvidencePoint:
    return EvidencePoint(
        "2026-07-16T00:00:00+00:00",
        ResourceSnapshot(
            "fam-parity-ollama",
            memory_peak_bytes=4_000,
            cpu_usage_microseconds=cpu,
            io_read_bytes=read_bytes,
            io_write_bytes=20,
            io_read_operations=1,
            io_write_operations=2,
        ),
        (NvidiaResourceReading(0, "GPU", 16_000, gpu_bytes, 0.5, "driver"),),
        models,
        BlockIoReading("storage-root", read_bytes, 20, 1, 2),
    )


class WorkstationEvidenceTests(unittest.TestCase):
    def test_records_cpu_ram_vram_io_and_fresh_model_residency(self) -> None:
        before = point(100, 10, 1_000)
        model = LoadedModel("expert", 5_000, 4_000, 2048)
        evidence = _evidence_payload(before, point(900, 2_010, 5_000, (model,)))

        self.assertEqual(evidence["deltas"]["cpu_usage_microseconds"], 800)
        self.assertEqual(evidence["deltas"]["io_read_bytes"], 2_000)
        self.assertEqual(
            evidence["accelerator_deltas"][0]["memory_used_delta_bytes"], 4_000
        )
        transfer = evidence["model_transfers"][0]
        self.assertEqual(transfer["resident_set_delta_bytes"], 5_000)
        self.assertEqual(transfer["accelerator_residency_delta_bytes"], 4_000)
        self.assertTrue(all(evidence["measurement_availability"].values()))

    def test_marks_missing_cgroup_measurements_unavailable(self) -> None:
        missing = EvidencePoint(
            "2026-07-16T00:00:00+00:00", None, (), (), None
        )
        availability = _evidence_payload(missing, missing)["measurement_availability"]
        self.assertFalse(any(availability.values()))


if __name__ == "__main__":
    unittest.main()
