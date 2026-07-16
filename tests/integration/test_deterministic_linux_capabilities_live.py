import os
import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.dbus_calls import (
    AllowlistedDbusAdapter, DbusBus, DbusCapabilitySpec, session_bus_environment,
)
from fam_os.adapters.linux.mime_types import ScopedMimeTypeAdapter
from fam_os.adapters.linux.desktop_portal import DesktopPortalAdapter, PortalOpenUriPolicy
from fam_os.adapters.linux.scoped_files import ScopedFileAdapter, ScopedFilePolicy
from fam_os.adapters.linux.tools import (
    AllowlistedToolAdapter, ToolCapabilitySpec, ToolOutputKind, ToolParameter,
)


@unittest.skipUnless(Path("/usr/bin/file").is_file(), "file utility is unavailable")
class LiveDeterministicLinuxCapabilityTests(unittest.TestCase):
    def test_scoped_file_mime_tool_and_session_bus_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "evidence.txt"
            path.write_text("FAM deterministic evidence\n")
            policy = ScopedFilePolicy((root,))
            observed = ScopedFileAdapter(policy).observe(path, include_content=True)
            mime = ScopedMimeTypeAdapter(policy).observe(path)
            tool = AllowlistedToolAdapter((_sha256_tool(),)).invoke(
                "tool.sha256", {"path": str(path)}
            )
        self.assertEqual(b"FAM deterministic evidence\n", observed.content)
        self.assertEqual("text/plain", mime.mime_type)
        self.assertTrue(tool.succeeded)
        self.assertIn(observed.sha256, tool.output["text"])

        if os.environ.get("DBUS_SESSION_BUS_ADDRESS") or os.environ.get("XDG_RUNTIME_DIR"):
            environment = session_bus_environment(os.environ)
            ping = AllowlistedDbusAdapter(
                (_peer_ping(),), environment=environment
            ).invoke("dbus.session.ping", {})
            self.assertTrue(ping.succeeded)
            portal = DesktopPortalAdapter(PortalOpenUriPolicy(
                ("https",), environment=tuple(environment.items())
            )).probe()
            self.assertTrue(portal.succeeded)


def _sha256_tool():
    return ToolCapabilitySpec(
        "tool.sha256", Path("/usr/bin/sha256sum"), (),
        (ToolParameter("path"),),
        {
            "type": "object", "properties": {"path": {"type": "string"}},
            "required": ["path"], "additionalProperties": False,
        },
        ToolOutputKind.TEXT,
    )


def _peer_ping():
    return DbusCapabilitySpec(
        "dbus.session.ping", DbusBus.USER, "org.freedesktop.DBus",
        "/org/freedesktop/DBus", "org.freedesktop.DBus.Peer", "Ping", (),
        {"type": "object", "additionalProperties": False},
    )


if __name__ == "__main__":
    unittest.main()
