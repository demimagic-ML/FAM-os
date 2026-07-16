import unittest
from collections import Counter

from fam_os.adapters.linux.accessibility import (
    AccessibilityBridgePolicy,
    GiAtspiProvider,
    LinuxAccessibilityBridge,
)


class LiveLinuxAccessibilityTests(unittest.TestCase):
    def test_current_session_observation_is_bounded_and_read_only(self):
        provider = GiAtspiProvider()
        if not provider.available():
            self.skipTest("AT-SPI is unavailable")
        roots = provider.roots()
        readable = []
        for root in roots:
            try:
                node = provider.read(root, 128)
            except Exception:
                continue
            if node.process_id > 0:
                readable.append((root, node.process_id))
        counts = Counter(process_id for _, process_id in readable)
        process_id = next((value for _, value in readable if counts[value] == 1), None)
        if process_id is None:
            self.skipTest("no unambiguous accessible application process")

        bridge = LinuxAccessibilityBridge(
            provider,
            AccessibilityBridgePolicy(
                maximum_nodes=64,
                maximum_depth=4,
                maximum_text_characters=128,
                maximum_actions_per_node=8,
            ),
        )
        snapshot = bridge.observe(process_id, include_text=False)

        self.assertGreater(len(snapshot.nodes), 0)
        self.assertLessEqual(len(snapshot.nodes), 64)
        self.assertTrue(all(node.text is None for node in snapshot.nodes))
        self.assertTrue(
            all(
                not node.protected
                or (node.name is None and node.description is None and not node.actions)
                for node in snapshot.nodes
            )
        )


if __name__ == "__main__":
    unittest.main()
