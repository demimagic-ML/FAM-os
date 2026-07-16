import unittest

from fam_os.adapters.linux import LinuxHardwareDiscovery
from rnf.profile import collect_profile


class LinuxProfileParityTests(unittest.TestCase):
    def test_matches_parent_profile_semantics(self) -> None:
        parent = collect_profile()
        profile = LinuxHardwareDiscovery().collect()

        self.assertEqual(profile.schema_version, parent["schema_version"])
        self.assertEqual(profile.hostname, parent["hostname"])
        self.assertEqual(profile.operating_system.system, parent["os"]["system"])
        self.assertEqual(profile.operating_system.release, parent["os"]["release"])
        self.assertEqual(profile.operating_system.machine, parent["os"]["machine"])
        self.assertEqual(profile.cpu.model, parent["cpu"]["model"])
        self.assertEqual(profile.cpu.logical_cpus, parent["cpu"]["logical_cpus"])
        self.assertEqual(profile.memory.total_bytes, parent["memory"]["total_bytes"])
        self.assertEqual(profile.memory.swap_total_bytes, parent["memory"]["swap_total_bytes"])
        self.assertEqual(profile.storage.root_total_bytes, parent["storage"]["root_total_bytes"])
        self.assertEqual([gpu.name for gpu in profile.gpus], [gpu["name"] for gpu in parent["gpus"]])
        self.assertEqual(profile.npu_device_paths, tuple(parent["npu_devices"]))
        self.assertEqual(profile.runtime_version("ollama"), parent["ollama"]["version"])


if __name__ == "__main__":
    unittest.main()

