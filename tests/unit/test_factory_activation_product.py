import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.core.production import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import (
    RuntimeModelCatalog,
    RuntimeModelProvenance,
)
from fam_os.expert_factory import decide_canary_activation
from fam_os.product.factory_activation import ProductFactoryActivation
from tests.unit.test_factory_canary import NOW, _approval, _report
from tests.unit.test_factory_specialist_packaging import _conversion, _lineage


class ProductFactoryActivationTests(unittest.TestCase):
    def test_confirmed_signed_success_updates_lifecycle_storage_and_live_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            lineage = _lineage(_conversion(Path(temporary)))
            approval = _approval()
            decision = decide_canary_activation(
                decision_id="activation-canary-1", approval=approval,
                report=_report(approval), signer_key_id="factory-canary-key-1",
                signing_key=Ed25519PrivateKey.from_private_bytes(b"c" * 32),
                decided_at=NOW,
            )
            package = SimpleNamespace(
                release_id=lineage.release_id, artifact_sha256="a" * 64,
            )
            release = _Release(decision, approval, package, lineage)
            enablement = _Enablement()
            repositories = SimpleNamespace(
                factory_releases=release, expert_enablement=enablement,
            )
            lifecycle = _Lifecycle()
            catalog = RuntimeModelCatalog(())
            state = ProductFactoryActivation(
                repositories, lifecycle, catalog,
            ).activate(canary_id=approval.one_use_canary_id, confirmed=True)
            self.assertEqual("activated-state", state)
            self.assertEqual(1, len(lifecycle.coordinates))
            self.assertEqual(1, len(enablement.values))
            self.assertIsNotNone(catalog.get(lineage.runtime_model_ref))
            self.assertTrue(catalog.remove_runtime_model(lineage.runtime_model_ref))
            self.assertIsNone(catalog.get(lineage.runtime_model_ref))
            self.assertFalse(catalog.remove_runtime_model(lineage.runtime_model_ref))

    def test_missing_confirmation_changes_nothing(self):
        service = ProductFactoryActivation(
            SimpleNamespace(), _Lifecycle(), RuntimeModelCatalog(()),
        )
        with self.assertRaisesRegex(PermissionError, "confirmation"):
            service.activate(canary_id="canary-1", confirmed=False)

    def test_unavailable_verifier_changes_no_activation_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            lineage = _lineage(_conversion(Path(temporary)))
            approval = _approval()
            decision = decide_canary_activation(
                decision_id="activation-canary-1", approval=approval,
                report=_report(approval), signer_key_id="factory-canary-key-1",
                signing_key=Ed25519PrivateKey.from_private_bytes(b"c" * 32),
                decided_at=NOW,
            )
            package = SimpleNamespace(
                release_id=lineage.release_id, artifact_sha256="a" * 64,
            )
            enablement = _Enablement()
            repositories = SimpleNamespace(
                factory_releases=_Release(
                    decision, approval, package, lineage,
                ),
                expert_enablement=enablement,
            )
            lifecycle = _Lifecycle()
            catalog = RuntimeModelCatalog(())
            catalog.require_available_verifiers(())

            with self.assertRaisesRegex(ValueError, "requires unavailable verifiers"):
                ProductFactoryActivation(
                    repositories, lifecycle, catalog,
                ).activate(canary_id=approval.one_use_canary_id, confirmed=True)

            self.assertEqual([], lifecycle.coordinates)
            self.assertEqual([], enablement.values)
            self.assertIsNone(catalog.get(lineage.runtime_model_ref))

    def test_existing_signed_model_reference_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            lineage = _lineage(_conversion(Path(temporary)))
            approval = _approval()
            decision = decide_canary_activation(
                decision_id="activation-canary-1", approval=approval,
                report=_report(approval), signer_key_id="factory-canary-key-1",
                signing_key=Ed25519PrivateKey.from_private_bytes(b"c" * 32),
                decided_at=NOW,
            )
            package = SimpleNamespace(
                release_id=lineage.release_id, artifact_sha256="a" * 64,
            )
            entry = RuntimeModelEntry(
                lineage.runtime_model_ref, "economical", (ModelIntent.CODE,),
                lineage.estimated_resident_bytes, lineage.max_context_tokens,
                "b" * 64, lineage.required_verifier_ids,
            )
            owner = RuntimeModelProvenance(
                entry.model_ref, "expert.signed-owner", "signed@1.0.0",
                "ollama.local/v1:signed", entry.intents, entry.verifier_ids,
            )
            catalog = RuntimeModelCatalog((entry,), (owner,))
            enablement = _Enablement()
            lifecycle = _Lifecycle()
            repositories = SimpleNamespace(
                factory_releases=_Release(
                    decision, approval, package, lineage,
                ),
                expert_enablement=enablement,
            )

            with self.assertRaisesRegex(ValueError, "already owned"):
                ProductFactoryActivation(
                    repositories, lifecycle, catalog,
                ).activate(canary_id=approval.one_use_canary_id, confirmed=True)

            self.assertEqual([], lifecycle.coordinates)
            self.assertEqual([], enablement.values)
            self.assertEqual(entry, catalog.get(entry.model_ref))


class _Release:
    def __init__(self, decision, approval, package, lineage):
        self._decision = decision
        self._approval = approval
        self._package = package
        self._lineage = lineage

    def activation_decision(self, canary_id):
        return self._decision

    def canary_approval(self, approval_id):
        return self._approval

    def package_receipt_by_sha(self, sha256):
        return self._package

    def lineage(self, release_id):
        return self._lineage


class _Enablement:
    def __init__(self):
        self.values = []

    def synchronize(self, provenance, entry):
        self.values.append((provenance, entry))


class _Lifecycle:
    def __init__(self):
        self.coordinates = []

    def activate(self, coordinate):
        self.coordinates.append(coordinate)
        return "activated-state"


if __name__ == "__main__":
    unittest.main()
