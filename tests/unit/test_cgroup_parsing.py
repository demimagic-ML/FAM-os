import unittest

from fam_os.adapters.cgroup.parsing import (
    parse_ceiling,
    parse_count_ceiling,
    parse_counter,
    parse_cpu_quota,
    parse_events,
    parse_io_limits,
    parse_pressure,
)
from fam_os.supervisor import PressureScope


class CgroupParsingTests(unittest.TestCase):
    def test_parses_unbounded_and_finite_ceilings(self) -> None:
        self.assertTrue(parse_ceiling("max\n").unbounded)
        self.assertEqual(parse_ceiling("16777216").maximum_bytes, 16_777_216)
        self.assertTrue(parse_count_ceiling("max").unbounded)
        self.assertEqual(parse_count_ceiling("8").maximum, 8)
        self.assertTrue(parse_cpu_quota("max 100000").unbounded)
        self.assertEqual(parse_cpu_quota("25000 100000").maximum_percent, 25.0)

    def test_rejects_negative_counter(self) -> None:
        with self.assertRaisesRegex(ValueError, "negative"):
            parse_counter("-1")

    def test_parses_named_events(self) -> None:
        events = parse_events("high 2\noom_kill 1\n")
        self.assertEqual([(event.name, event.count) for event in events], [
            ("high", 2), ("oom_kill", 1)
        ])

    def test_parses_pressure_samples(self) -> None:
        samples = parse_pressure("some avg10=0.1 avg60=0.2 avg300=0.3 total=42\n")
        self.assertEqual(samples[0].scope, PressureScope.SOME)
        self.assertEqual(samples[0].average_60, 0.2)
        self.assertEqual(samples[0].total_stall_microseconds, 42)

    def test_parses_block_io_bandwidth_ceilings(self) -> None:
        limits = parse_io_limits(
            "259:0 rbps=1000000000 wbps=256000000 riops=max wiops=max\n"
        )
        self.assertEqual(limits[0].device_major, 259)
        self.assertEqual(limits[0].read_bytes_per_second, 1_000_000_000)
        self.assertEqual(limits[0].write_bytes_per_second, 256_000_000)


if __name__ == "__main__":
    unittest.main()
