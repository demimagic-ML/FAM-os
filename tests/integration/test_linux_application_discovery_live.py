import os
import unittest
from pathlib import Path

from fam_os.adapters.linux import (
    LinuxApplicationDiscovery, application_discovery_settings,
)


@unittest.skipUnless(Path("/proc").is_dir(), "Linux procfs is unavailable")
class LiveLinuxApplicationDiscoveryTests(unittest.TestCase):
    def test_current_machine_read_only_snapshot(self):
        settings = application_discovery_settings(os.environ, Path.home())
        snapshot = LinuxApplicationDiscovery.standard(settings).collect()
        self.assertGreater(len(snapshot.processes), 0)
        self.assertGreater(len(snapshot.applications), 0)
        self.assertTrue(all(item.title is None for item in snapshot.windows))
        self.assertTrue(
            snapshot.windows or any(
                issue.surface.value == "windows" for issue in snapshot.issues
            )
        )


if __name__ == "__main__":
    unittest.main()
