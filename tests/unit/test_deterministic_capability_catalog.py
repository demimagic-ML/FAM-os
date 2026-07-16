import unittest
from datetime import datetime, timezone

from fam_os.adapters.linux.deterministic_catalog import (
    build_deterministic_registration, file_observation, file_write,
    mime_observation, portal_open_uri,
)
from fam_os.applications import (
    ApplicationCapabilityRegistry, ConfirmationPolicy, Reversibility,
)


class DeterministicCapabilityCatalogTests(unittest.TestCase):
    def test_builtins_register_with_scopes_and_conservative_action_policy(self):
        declarations = (
            file_observation(("file:///workspace",)),
            file_write(("file:///workspace",)),
            mime_observation(("file:///workspace",)),
            portal_open_uri(("https",)),
        )
        registration = build_deterministic_registration(
            "connector-linux-tools", "instance-linux-tools", declarations,
            datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc),
        )
        registry = ApplicationCapabilityRegistry()
        registry.register(registration)
        self.assertEqual(4, len(registry.entries()))
        write = registry.lookup("instance-linux-tools", "linux.file.atomic_write")
        self.assertEqual(Reversibility.IRREVERSIBLE, write.capability.reversibility)
        self.assertEqual(ConfirmationPolicy.ALWAYS, write.capability.confirmation)
        self.assertEqual(("file.sha256",), write.capability.postcondition_ids)
        portal = registry.lookup("instance-linux-tools", "linux.portal.open_uri")
        self.assertEqual(("scheme:https",), portal.resource_scopes)


if __name__ == "__main__":
    unittest.main()
