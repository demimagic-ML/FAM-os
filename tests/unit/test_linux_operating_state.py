import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.operating_state import (
    GNOME_IDLE_QUERY,
    NVIDIA_TEMPERATURE_QUERY,
    LinuxOperatingStateObserver,
)


class LinuxOperatingStateObserverTests(unittest.TestCase):
    def test_observes_battery_hottest_sensor_load_and_desktop_idle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            battery = root / "power/BAT0"
            battery.mkdir(parents=True)
            (battery / "type").write_text("Battery\n")
            (battery / "capacity").write_text("17\n")
            (battery / "status").write_text("Discharging\n")
            zone = root / "thermal/thermal_zone0"
            zone.mkdir(parents=True)
            (zone / "temp").write_text("68000\n")
            loadavg = root / "loadavg"
            loadavg.write_text("4.0 3.0 2.0 1/100 1\n")
            runner = _Runner({
                NVIDIA_TEMPERATURE_QUERY: "72\n",
                GNOME_IDLE_QUERY: "(uint64 600000,)",
            })

            observed = LinuxOperatingStateObserver(
                runner, root / "power", root / "thermal", root / "hwmon",
                loadavg, lambda: 8,
            ).observe()

            self.assertEqual(17, observed.state.battery_percent)
            self.assertFalse(observed.state.charging)
            self.assertEqual(72, observed.state.thermal_celsius)
            self.assertEqual(0.5, observed.state.foreground_load)
            self.assertEqual(600, observed.state.idle_seconds)
            self.assertEqual((), observed.reason_codes)

    def test_missing_authoritative_readings_fail_closed_for_background_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observed = LinuxOperatingStateObserver(
                _Runner({}), root / "power", root / "thermal", root / "hwmon",
                root / "missing-loadavg", lambda: None,
            ).observe()

            self.assertIsNone(observed.state.thermal_celsius)
            self.assertEqual(1.0, observed.state.foreground_load)
            self.assertEqual(0, observed.state.idle_seconds)
            self.assertIn("thermal.reading_unavailable", observed.reason_codes)
            self.assertIn("foreground.load_unavailable", observed.reason_codes)
            self.assertIn("idle.reading_unavailable", observed.reason_codes)


class _Runner:
    def __init__(self, outputs):
        self.outputs = outputs

    def run(self, command, timeout_seconds=10.0):
        del timeout_seconds
        return self.outputs.get(command)


if __name__ == "__main__":
    unittest.main()
