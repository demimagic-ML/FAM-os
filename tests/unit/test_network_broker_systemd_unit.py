import unittest
from pathlib import Path


class NetworkBrokerSystemdUnitTests(unittest.TestCase):
    def test_root_broker_never_executes_owner_installation_or_pythonpath(self):
        value = Path("packaging/systemd/fam-network-broker.service").read_text()
        self.assertIn(
            "ConditionFileIsExecutable=/usr/libexec/fam-os-network/bin/fam-network-broker",
            value,
        )
        self.assertIn(
            "ExecStart=/usr/libexec/fam-os-network/bin/fam-network-broker", value,
        )
        self.assertIn(
            "--installation-prefix /usr/libexec/fam-os-network", value,
        )
        self.assertNotIn("PYTHONPATH", value)
        self.assertNotIn("@FAM_PREFIX@", value)
        self.assertIn("ConditionPathIsDirectory=/run/netns", value)
        self.assertIn("ReadWritePaths=/run/fam-os-network /run/netns", value)
        self.assertIn("NoNewPrivileges=true", value)
        self.assertIn(
            "CapabilityBoundingSet=CAP_NET_ADMIN CAP_SYS_ADMIN", value,
        )

    def test_owner_service_network_client_configuration_is_optional(self):
        value = Path("packaging/systemd/fam-os.service").read_text()
        self.assertIn(
            "EnvironmentFile=-%h/.config/fam-os/network-client.env", value,
        )


if __name__ == "__main__":
    unittest.main()
