import tempfile
import base64
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from fam_os.adapters.integration.network_broker_handler import (
    IntegrationNetworkBrokerHandler,
)
from fam_os.adapters.integration.network_broker_state import (
    NetworkBrokerStateStore, network_enforcement_id,
)
from fam_os.core.engineering import (
    IntegrationNetworkAttachmentKind, IntegrationNetworkEnforcementRequest,
)
from fam_os.supervisor import (
    NetworkAttachment, NetworkEnforcementLease, NetworkUsageSnapshot,
)
from tests.contract.schema_integration_environment_fixtures import NOW


class Controller:
    def __init__(self): self.calls = []
    def open(self, context, spec, instant):
        self.calls.append(("open", context, spec, instant))
        return NetworkEnforcementLease(
            spec.enforcement_id, (NetworkAttachment(
                spec.attachment_kinds[0], "/run/netns/" + spec.enforcement_id,
                "http://10.0.0.1:8080",
            ),), spec.destinations,
            spec.maximum_network_bytes, NOW, spec.expires_at, "b" * 64,
        )
    def observe(self, context, identity):
        self.calls.append(("observe", context, identity))
        return self._usage(identity, False)
    def close(self, context, identity):
        self.calls.append(("close", context, identity))
        return self._usage(identity, True)
    def recover(self, context, spec):
        self.calls.append(("recover", context, spec))
        return self._usage(spec.enforcement_id, True)
    def _usage(self, identity, finalized):
        return NetworkUsageSnapshot(
            identity, ("registry.example:443",), 10, 20, 10_000,
            False, finalized, NOW, "c" * 64,
        )


class FailingCloseController(Controller):
    def close(self, context, identity):
        self.calls.append(("close", context, identity))
        raise OSError("deliberate close failure")


class FailingActivationStore(NetworkBrokerStateStore):
    def activate(self, request, lease): raise OSError("state unavailable")


class Verifier:
    def __init__(self, accepted=True): self.accepted, self.calls = accepted, []
    def verify(self, request):
        self.calls.append(request)
        if not self.accepted: raise PermissionError("signature denied")


class Authorities:
    def __init__(self): self.active = set()
    def admit(self, request, identity): self.active.add(identity)
    def retire(self, identity): self.active.discard(identity)


class IntegrationNetworkBrokerHandlerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "state"
        self.request = IntegrationNetworkEnforcementRequest(
            "network-request-1", "environment-1", "permit-1", "host-1",
            "fam-core", "session-1", "authority-network-1", "device-key-1",
            base64.b64encode(b"\0" * 64).decode(), "a" * 64,
            (IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,),
            ("registry.example:443",), 10_000, NOW + timedelta(minutes=5),
        )

    def _handler(
        self, controller=None, store=None, verifier=None, authorities=None,
    ):
        return IntegrationNetworkBrokerHandler(
            controller or Controller(), store or NetworkBrokerStateStore(self.root),
            lambda: NOW, verifier or Verifier(), authorities or Authorities(),
        )

    def test_open_observe_close_is_durable_and_exact(self):
        controller = Controller(); handler = self._handler(controller)
        lease = handler.open(self.request)
        self.assertEqual(self.request.principal_id, lease.principal_id)
        self.assertFalse(handler.observe(lease).finalized)
        closed = handler.close(lease)
        self.assertTrue(closed.finalized)
        document = NetworkBrokerStateStore(self.root).load(lease.enforcement_id)
        self.assertEqual("closed", document["state"])
        self.assertEqual(closed, self._handler().recover(self.request))

    def test_substituted_lease_is_rejected_before_supervisor_effect(self):
        controller = Controller(); handler = self._handler(controller)
        lease = handler.open(self.request); before = len(controller.calls)
        with self.assertRaisesRegex(PermissionError, "not exact"):
            handler.observe(replace(lease, authority_ref="authority-other"))
        self.assertEqual(before, len(controller.calls))

    def test_restart_recovers_opening_intent_without_normal_lease(self):
        store = NetworkBrokerStateStore(self.root)
        identity = store.begin(self.request)
        controller = Controller()
        recovered = self._handler(controller, store).recover(self.request)
        self.assertTrue(recovered.finalized)
        self.assertEqual("recover", controller.calls[0][0])
        self.assertEqual("recovered", store.load(identity)["state"])

    def test_activation_persistence_failure_compensates(self):
        controller = Controller()
        handler = self._handler(controller, FailingActivationStore(self.root))
        with self.assertRaisesRegex(OSError, "state unavailable"):
            handler.open(self.request)
        self.assertEqual(["open", "close"], [item[0] for item in controller.calls])
        identity = network_enforcement_id(self.request.environment_id)
        self.assertEqual(
            "compensated", NetworkBrokerStateStore(self.root).load(identity)["state"],
        )

    def test_environment_identity_is_single_use(self):
        handler = self._handler(); handler.open(self.request)
        with self.assertRaises(FileExistsError):
            handler.open(replace(self.request, request_id="network-request-2"))

    def test_invalid_signature_is_denied_before_state_or_supervisor(self):
        controller = Controller()
        with self.assertRaisesRegex(PermissionError, "signature denied"):
            self._handler(controller, verifier=Verifier(False)).open(self.request)
        self.assertEqual([], controller.calls)
        self.assertFalse(self.root.exists())

    def test_recovery_mismatch_and_compensation_failure_retire_authority(self):
        store = NetworkBrokerStateStore(self.root); store.begin(self.request)
        authorities = Authorities()
        with self.assertRaisesRegex(PermissionError, "differs from intent"):
            self._handler(store=store, authorities=authorities).recover(
                replace(self.request, request_id="network-request-other"),
            )
        self.assertEqual(set(), authorities.active)

        other_root = Path(self.temporary.name).resolve() / "other-state"
        authorities = Authorities()
        with self.assertRaisesRegex(RuntimeError, "compensation is incomplete"):
            self._handler(
                FailingCloseController(), FailingActivationStore(other_root),
                authorities=authorities,
            ).open(replace(self.request, environment_id="environment-other"))
        self.assertEqual(set(), authorities.active)


if __name__ == "__main__":
    unittest.main()
