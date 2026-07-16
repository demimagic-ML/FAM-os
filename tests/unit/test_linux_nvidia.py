import unittest
from pathlib import Path

from fam_os.adapters.linux.nvidia import (
    NVIDIA_QUERY,
    NVIDIA_RESOURCE_QUERY,
    parse_nvidia_resources,
    parse_nvidia_smi,
    query_nvidia_gpus,
    query_nvidia_resources,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "linux" / "nvidia-smi.csv"


class FakeRunner:
    def __init__(self, output: str | None) -> None:
        self.output = output
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...], timeout_seconds: float = 10.0) -> str | None:
        self.commands.append(command)
        return self.output


class NvidiaParserTests(unittest.TestCase):
    def test_parses_numeric_gpu_fields(self) -> None:
        gpu = parse_nvidia_smi(FIXTURE.read_text())[0]
        self.assertEqual(gpu.name, "FAM Test GPU")
        self.assertEqual(gpu.memory_total_bytes, 16 * 1024**3)
        self.assertEqual(gpu.power_limit_watts, 250.0)

    def test_missing_nvidia_smi_degrades_to_no_gpus(self) -> None:
        runner = FakeRunner(None)
        self.assertEqual(query_nvidia_gpus(runner), ())
        self.assertEqual(runner.commands, [NVIDIA_QUERY])

    def test_parses_privacy_safe_resource_fields(self) -> None:
        reading = parse_nvidia_resources(
            "0, FAM Test GPU, 16384, 2048, 25, 600.1\n"
        )[0]
        self.assertEqual(reading.index, 0)
        self.assertEqual(reading.memory_total_bytes, 16 * 1024**3)
        self.assertEqual(reading.memory_used_bytes, 2 * 1024**3)
        self.assertEqual(reading.utilization_fraction, 0.25)

    def test_missing_resource_query_degrades_to_no_readings(self) -> None:
        runner = FakeRunner(None)
        self.assertEqual(query_nvidia_resources(runner), ())
        self.assertEqual(runner.commands, [NVIDIA_RESOURCE_QUERY])


if __name__ == "__main__":
    unittest.main()
