import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.bubblewrap import (
    BubblewrapAccessResource,
    BubblewrapServiceAccessAdapter,
)
from fam_os.supervisor import (
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    ResourceLimits,
    ServiceAccessGrant,
    ServiceDefinition,
    SupervisorAuthorizationError,
)


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def access_grant(
    grant_id: str,
    service_id: str,
    resource_id: str,
    kind: AccessResourceKind,
    mode: AccessMode,
    *,
    expires_at: datetime = NOW + timedelta(hours=1),
) -> ServiceAccessGrant:
    return ServiceAccessGrant(
        grant_id,
        "authority",
        "principal",
        "session",
        service_id,
        resource_id,
        kind,
        mode,
        NOW - timedelta(minutes=1),
        expires_at,
    )


def resource(resource_id: str, kind: AccessResourceKind, mode: AccessMode):
    return AccessResourceDescriptor(resource_id, kind, (mode,))


class BubblewrapServiceAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = BubblewrapServiceAccessAdapter(
            (
                BubblewrapAccessResource(
                    "filesystem.models",
                    AccessResourceKind.FILESYSTEM,
                    Path("/host/models"),
                    Path("/access/models"),
                ),
                BubblewrapAccessResource(
                    "device.gpu-0",
                    AccessResourceKind.DEVICE,
                    Path("/dev/nvidia0"),
                    Path("/dev/nvidia0"),
                ),
            ),
            clock=lambda: NOW,
        )

    def test_projects_active_filesystem_and_device_grants(self) -> None:
        filesystem = access_grant(
            "grant-files", "fam-a", "filesystem.models",
            AccessResourceKind.FILESYSTEM, AccessMode.READ,
        )
        device = access_grant(
            "grant-device", "fam-a", "device.gpu-0",
            AccessResourceKind.DEVICE, AccessMode.READ_WRITE,
        )
        self.adapter.grant(
            filesystem,
            resource("filesystem.models", AccessResourceKind.FILESYSTEM, AccessMode.READ),
        )
        self.adapter.grant(
            device,
            resource("device.gpu-0", AccessResourceKind.DEVICE, AccessMode.READ_WRITE),
        )
        limits = ResourceLimits(memory_max_bytes=64 * 1024 * 1024)
        definition = ServiceDefinition(
            "fam-a", ("/usr/bin/model", "serve"), (("MODE", "test"),), limits
        )

        projected = self.adapter.project(definition)

        self.assertEqual(definition.service_id, projected.service_id)
        self.assertEqual(definition.environment, projected.environment)
        self.assertEqual(definition.limits, projected.limits)
        self.assertBinding(
            projected.command, "--ro-bind", "/host/models", "/access/models"
        )
        self.assertBinding(
            projected.command, "--dev-bind", "/dev/nvidia0", "/dev/nvidia0"
        )
        self.assertEqual(("/usr/bin/model", "serve"), projected.command[-2:])
        self.assertEqual("--", projected.command[-3])
        self.assertEqual(1, projected.command.count("/dev"))

    def test_revoke_and_service_scope_remove_bindings(self) -> None:
        grant = access_grant(
            "grant-files", "fam-a", "filesystem.models",
            AccessResourceKind.FILESYSTEM, AccessMode.READ,
        )
        descriptor = resource(
            "filesystem.models", AccessResourceKind.FILESYSTEM, AccessMode.READ
        )
        self.adapter.grant(grant, descriptor)
        other = self.adapter.project(ServiceDefinition("fam-b", ("/usr/bin/true",)))
        self.assertNotIn("/host/models", other.command)

        self.adapter.revoke(grant, descriptor)
        projected = self.adapter.project(
            ServiceDefinition("fam-a", ("/usr/bin/true",))
        )
        self.assertNotIn("/host/models", projected.command)

    def test_expired_grant_is_not_projected(self) -> None:
        expired = access_grant(
            "grant-expired", "fam-a", "filesystem.models",
            AccessResourceKind.FILESYSTEM, AccessMode.READ, expires_at=NOW,
        )
        descriptor = resource(
            "filesystem.models", AccessResourceKind.FILESYSTEM, AccessMode.READ
        )
        self.adapter.grant(expired, descriptor)
        projected = self.adapter.project(
            ServiceDefinition("fam-a", ("/usr/bin/true",))
        )
        self.assertNotIn("/host/models", projected.command)

    def test_write_only_and_unmapped_resources_are_rejected(self) -> None:
        write = access_grant(
            "grant-write", "fam-a", "filesystem.models",
            AccessResourceKind.FILESYSTEM, AccessMode.WRITE,
        )
        with self.assertRaisesRegex(SupervisorAuthorizationError, "write-only"):
            self.adapter.grant(
                write,
                resource("filesystem.models", AccessResourceKind.FILESYSTEM, AccessMode.WRITE),
            )
        unknown = access_grant(
            "grant-unknown", "fam-a", "filesystem.unknown",
            AccessResourceKind.FILESYSTEM, AccessMode.READ,
        )
        with self.assertRaisesRegex(SupervisorAuthorizationError, "no Bubblewrap"):
            self.adapter.grant(
                unknown,
                resource("filesystem.unknown", AccessResourceKind.FILESYSTEM, AccessMode.READ),
            )

    def test_resource_mapping_cannot_replace_runtime_or_device_roots(self) -> None:
        invalid = (
            (AccessResourceKind.FILESYSTEM, "/host/models", "/usr/models"),
            (AccessResourceKind.FILESYSTEM, "/host/models", "/access"),
            (AccessResourceKind.DEVICE, "/host/device", "/dev/nvidia0"),
            (AccessResourceKind.DEVICE, "/dev/nvidia0", "/access/gpu"),
        )
        for kind, source, target in invalid:
            with self.subTest(kind=kind, target=target):
                with self.assertRaises(ValueError):
                    BubblewrapAccessResource(
                        "filesystem.invalid", kind, Path(source), Path(target)
                    )

    def assertBinding(
        self, command: tuple[str, ...], flag: str, source: str, destination: str
    ) -> None:
        expected = (flag, source, destination)
        windows = tuple(zip(command, command[1:], command[2:]))
        self.assertIn(expected, windows)


if __name__ == "__main__":
    unittest.main()
