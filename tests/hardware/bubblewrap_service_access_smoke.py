"""Opt-in live proof of allowlisted filesystem access in a service namespace."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.bubblewrap import (
    BubblewrapAccessResource,
    BubblewrapServiceAccessAdapter,
)
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.systemd import SystemdUserServiceLifecycle
from fam_os.adapters.systemd import SystemdUserSettings
from fam_os.supervisor import (
    AccessMode,
    AccessResourceDescriptor,
    AccessResourceKind,
    InMemoryAccessGrantRegistry,
    InMemoryAccessResourceCatalog,
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ServiceAccessController,
    ServiceAccessGrant,
    ServiceDefinition,
    ServiceState,
    SupervisorCallContext,
    SupervisorCapability,
)


SERVICE_ID = "fam-phase34-smoke"
FILE_RESOURCE_ID = "filesystem.phase34-proof"
DEVICE_RESOURCE_ID = "device.phase34-null"
ROOT = Path(__file__).parents[2]


class ExactAuthorizer:
    def require(self, context, capability, service_id) -> None:
        expected = {
            SupervisorCapability.START_UNPRIVILEGED_SERVICE,
            SupervisorCapability.STOP_OWNED_SERVICE,
            SupervisorCapability.GRANT_DECLARED_FILESYSTEM_ACCESS,
            SupervisorCapability.GRANT_DECLARED_DEVICE_ACCESS,
        }
        if capability not in expected or service_id != SERVICE_ID:
            raise AssertionError("unexpected filesystem-access authority")


@unittest.skipUnless(
    os.environ.get("FAM_BUBBLEWRAP_ACCESS_SMOKE") == "1",
    "set FAM_BUBBLEWRAP_ACCESS_SMOKE=1 for the live access test",
)
class BubblewrapServiceAccessSmokeTests(unittest.TestCase):
    def test_only_allowlisted_file_and_device_are_visible(self) -> None:
        now = datetime.now(timezone.utc)
        adapter = _access_adapter(now)
        lifecycle = SystemdUserServiceLifecycle(
            SubprocessCommandRunner(),
            SystemdUserSettings(apparmor_profile=_current_apparmor_profile()),
            projector=adapter,
        )
        authorizer = ExactAuthorizer()
        ownership = InMemoryServiceOwnershipRegistry()
        owned = OwnedServiceLifecycle(lifecycle, authorizer, ownership)
        controller = _access_controller(authorizer, ownership, adapter)
        context = SupervisorCallContext(
            "phase34-request", "local-principal", "local-session", "phase34-authority"
        )
        definition = ServiceDefinition(SERVICE_ID, _proof_command())
        grants = (
            _grant("phase34-file", context, FILE_RESOURCE_ID,
                   AccessResourceKind.FILESYSTEM, AccessMode.READ, now),
            _grant("phase34-device", context, DEVICE_RESOURCE_ID,
                   AccessResourceKind.DEVICE, AccessMode.READ_WRITE, now),
        )
        owned.declare(context, definition)
        for grant in grants:
            controller.grant(context, grant, now)
        try:
            self.assertEqual(ServiceState.ACTIVE, owned.start(context, definition).state)
        finally:
            owned.stop(context, SERVICE_ID)
            for grant in grants:
                controller.revoke(context, grant.grant_id, now)
        self.assertEqual(ServiceState.INACTIVE, lifecycle.status(SERVICE_ID).state)


def _access_adapter(now: datetime) -> BubblewrapServiceAccessAdapter:
    resources = (
        BubblewrapAccessResource(
            FILE_RESOURCE_ID, AccessResourceKind.FILESYSTEM,
            ROOT / "AGENTS.md", Path("/access/allowed.md"),
        ),
        BubblewrapAccessResource(
            DEVICE_RESOURCE_ID, AccessResourceKind.DEVICE,
            Path("/dev/null"), Path("/dev/fam-null"),
        ),
    )
    return BubblewrapServiceAccessAdapter(resources, clock=lambda: now)


def _access_controller(authorizer, ownership, adapter) -> ServiceAccessController:
    resources = (
        AccessResourceDescriptor(
            FILE_RESOURCE_ID, AccessResourceKind.FILESYSTEM, (AccessMode.READ,)
        ),
        AccessResourceDescriptor(
            DEVICE_RESOURCE_ID, AccessResourceKind.DEVICE, (AccessMode.READ_WRITE,)
        ),
    )
    return ServiceAccessController(
        authorizer, ownership, InMemoryAccessResourceCatalog(resources),
        InMemoryAccessGrantRegistry(), adapter,
    )


def _grant(grant_id, context, resource_id, kind, mode, now) -> ServiceAccessGrant:
    return ServiceAccessGrant(
        grant_id, context.authority_ref, context.principal_id, context.session_id,
        SERVICE_ID, resource_id, kind, mode,
        now - timedelta(seconds=1), now + timedelta(minutes=5),
    )


def _proof_command() -> tuple[str, ...]:
    program = (
        "from pathlib import Path; import time; "
        "allowed=Path('/access/allowed.md'); "
        "assert allowed.is_file() and allowed.read_text().startswith('#'); "
        "assert not Path('/home').exists(); "
        "assert Path('/dev/fam-null').is_char_device(); "
        "Path('/dev/fam-null').write_bytes(b'proof'); time.sleep(15)"
    )
    return "/usr/bin/python3", "-c", program


def _current_apparmor_profile() -> str:
    label = Path("/proc/self/attr/current").read_text().strip()
    profile = label.split(" ", 1)[0]
    if profile == "unconfined":
        raise unittest.SkipTest("a named AppArmor profile authorizing userns is required")
    return profile


if __name__ == "__main__":
    unittest.main()
