import unittest
from pathlib import Path

from fam_os.adapters.linux.procfs import parse_cpu_model, parse_meminfo


FIXTURES = Path(__file__).parents[1] / "fixtures" / "linux"


class MeminfoParserTests(unittest.TestCase):
    def test_converts_kernel_kibibytes_to_bytes(self) -> None:
        values = parse_meminfo((FIXTURES / "proc" / "meminfo").read_text())
        self.assertEqual(values["MemTotal"], 16 * 1024**3)
        self.assertEqual(values["MemAvailable"], 8 * 1024**3)
        self.assertEqual(values["SwapTotal"], 0)

    def test_skips_malformed_values(self) -> None:
        self.assertEqual(parse_meminfo("MemTotal: invalid kB\n"), {})


class CpuinfoParserTests(unittest.TestCase):
    def test_reads_x86_model_name(self) -> None:
        content = (FIXTURES / "proc" / "cpuinfo").read_text()
        self.assertEqual(parse_cpu_model(content), "FAM Test CPU 1.0")

    def test_supports_arm_hardware_name(self) -> None:
        self.assertEqual(parse_cpu_model("Hardware: FAM ARM Board\n"), "FAM ARM Board")


if __name__ == "__main__":
    unittest.main()

