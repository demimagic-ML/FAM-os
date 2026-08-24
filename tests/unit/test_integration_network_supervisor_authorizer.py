import base64
import unittest
from dataclasses import replace
from datetime import timedelta

from fam_os.adapters.integration.network_authorizer import (
    VerifiedNetworkSupervisorAuthorizer,
)
from fam_os.core.engineering import (
    IntegrationNetworkAttachmentKind, IntegrationNetworkEnforcementRequest,
)
from fam_os.supervisor import (
    SupervisorAuthorizationError, SupervisorCallContext, SupervisorCapability,
)
from tests.contract.schema_integration_environment_fixtures import NOW


class IntegrationNetworkSupervisorAuthorizerTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.authorizer = VerifiedNetworkSupervisorAuthorizer(lambda: self.now)
        self.request = IntegrationNetworkEnforcementRequest(
            "request-1", "environment-1", "permit-1", "host-1", "fam-core",
            "session-1", "authority-1", "device-key-1",
            base64.b64encode(b"\0" * 64).decode(), "a" * 64,
            (IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,),
            ("registry.example:443",), 1_000, NOW + timedelta(minutes=1),
        )
        self.context = SupervisorCallContext(
            self.request.request_id, self.request.principal_id,
            self.request.session_id, self.request.authority_ref,
        )

    def test_exact_verified_grant_admits_repeated_lifecycle_then_retires(self):
        identity = "fam-network-test"
        self.authorizer.admit(self.request, identity)
        for _ in range(2):
            self.authorizer.require(
                self.context, SupervisorCapability.ENFORCE_ALLOWLISTED_NETWORK,
                identity,
            )
        self.authorizer.retire(identity)
        with self.assertRaisesRegex(SupervisorAuthorizationError, "inactive"):
            self.authorizer.require(
                self.context, SupervisorCapability.ENFORCE_ALLOWLISTED_NETWORK,
                identity,
            )

    def test_context_conflict_expiry_and_other_capability_fail(self):
        identity = "fam-network-test"
        self.authorizer.admit(self.request, identity)
        with self.assertRaisesRegex(SupervisorAuthorizationError, "mismatched"):
            self.authorizer.require(
                replace(self.context, session_id="other-session"),
                SupervisorCapability.ENFORCE_ALLOWLISTED_NETWORK, identity,
            )
        with self.assertRaisesRegex(SupervisorAuthorizationError, "capability"):
            self.authorizer.require(
                self.context, SupervisorCapability.START_UNPRIVILEGED_SERVICE,
                identity,
            )
        self.now = self.request.expires_at
        with self.assertRaisesRegex(SupervisorAuthorizationError, "inactive"):
            self.authorizer.require(
                self.context, SupervisorCapability.ENFORCE_ALLOWLISTED_NETWORK,
                identity,
            )


if __name__ == "__main__":
    unittest.main()
