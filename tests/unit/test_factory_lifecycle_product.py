"""Product coordination tests for specialist retirement and audit retention."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.product.factory_lifecycle import ProductFactoryLifecycle, _runtime_model
from fam_os.registry.lifecycle import ExpertPackageLifecycle
from fam_os.adapters.filesystem import ImmutablePackageArtifactStore
from tests.unit.test_factory_specialist_packaging import (
    _conversion,
    _lineage,
    _packager,
)


class _LifecycleAudit:
    def __init__(self) -> None:
        self.request_value = None
        self.receipt_value = None

    def request(self, request_id):
        return self.request_value if self.request_value and self.request_value.request_id == request_id else None

    def begin(self, value):
        self.request_value = value
        return True

    def receipt_for_request(self, request_id):
        return self.receipt_value if self.receipt_value and self.receipt_value.request_id == request_id else None

    def complete(self, value):
        self.receipt_value = value

    def pending(self):
        return () if self.receipt_value is not None else (
            () if self.request_value is None else (self.request_value,)
        )

    def receipts(self):
        return () if self.receipt_value is None else (self.receipt_value,)


class _Enablement:
    def __init__(self) -> None:
        self.enabled = True

    def synchronize(self, provenance, entry):
        self.enabled = True

    def set_enabled(self, expert_id, enabled):
        self.enabled = enabled
        return True


class _Installer:
    def __init__(self) -> None:
        self.removed: list[str] = []

    def create(self, model_ref, modelfile):
        return "a" * 64

    def remove(self, model_ref):
        self.removed.append(model_ref)


class ProductFactoryLifecycleTests(unittest.TestCase):
    def test_confirmed_retirement_removes_routing_and_bytes_but_retains_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            conversion = _conversion(root)
            lineage = _lineage(conversion)
            package_root = root / "package-state"
            packager, state_store = _packager(
                package_root,
                Ed25519PrivateKey.from_private_bytes(b"p" * 32),
            )
            packaged = packager.package(lineage, conversion)
            lifecycle = ExpertPackageLifecycle(
                state_store,
                ImmutablePackageArtifactStore(package_root / "installed"),
            )
            coordinate = ExpertPackageCoordinate(
                lineage.package_id, lineage.package_version,
            )
            active = lifecycle.activate(coordinate)
            release_repository = SimpleNamespace(
                lineage=lambda release_id: (
                    lineage if release_id == lineage.release_id else None
                ),
                package_receipts=lambda: (packaged.receipt,),
                lineages=lambda: (lineage,),
            )
            repositories = SimpleNamespace(
                factory_releases=release_repository,
                factory_lifecycle=_LifecycleAudit(),
                expert_enablement=_Enablement(),
            )
            entry, provenance = _runtime_model(lineage, packaged.receipt)
            repositories.expert_enablement.synchronize(provenance, entry)
            catalog = RuntimeModelCatalog(())
            catalog.install_runtime_model(entry, provenance)
            installer = _Installer()
            service = ProductFactoryLifecycle(
                repositories=repositories, lifecycle=lifecycle,
                catalog=catalog, installer=installer,
                artifact_root=package_root / "installed",
                workspace_root=root / "lifecycle-workspace",
            )
            receipt = service.retire(
                request_id="retire-specialist-1",
                release_id=lineage.release_id,
                expected_lifecycle_revision=active.revision,
                reason_code="owner-requested-retirement",
                remove_artifact=True, confirmed=True,
            )
            self.assertTrue(receipt.artifact_removed)
            self.assertTrue(receipt.audit_retained)
            self.assertIsNone(catalog.get(lineage.runtime_model_ref))
            self.assertEqual([lineage.runtime_model_ref], installer.removed)
            self.assertEqual((), state_store.load().packages)
            self.assertEqual(lineage, release_repository.lineage(lineage.release_id))
            self.assertEqual((receipt,), service.receipts())

    def test_signed_production_failure_forces_active_specialist_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            conversion = _conversion(root)
            lineage = _lineage(conversion)
            package_root = root / "package-state"
            packager, state_store = _packager(
                package_root,
                Ed25519PrivateKey.from_private_bytes(b"p" * 32),
            )
            packaged = packager.package(lineage, conversion)
            lifecycle = ExpertPackageLifecycle(
                state_store,
                ImmutablePackageArtifactStore(package_root / "installed"),
            )
            lifecycle.activate(ExpertPackageCoordinate(
                lineage.package_id, lineage.package_version,
            ))
            entry, provenance = _runtime_model(lineage, packaged.receipt)
            catalog = RuntimeModelCatalog(())
            catalog.install_runtime_model(entry, provenance)
            audit = _LifecycleAudit()
            repositories = SimpleNamespace(
                factory_releases=SimpleNamespace(
                    lineages=lambda: (lineage,),
                    lineage=lambda release_id: lineage,
                    package_receipts=lambda: (packaged.receipt,),
                ),
                factory_lifecycle=audit,
                expert_enablement=_Enablement(),
            )
            installer = _Installer()
            service = ProductFactoryLifecycle(
                repositories=repositories, lifecycle=lifecycle,
                catalog=catalog, installer=installer,
                artifact_root=package_root / "installed",
                workspace_root=root / "lifecycle-workspace",
            )
            run = SimpleNamespace(
                status=SimpleNamespace(value="failed"),
                effective_trust="signed", acceptance_id="acceptance-1",
                candidate_id="candidate-1", request_id="request-1",
                verification_id="verification-1",
                verified_artifact_sha256="f" * 64,
            )
            record = SimpleNamespace(selection=SimpleNamespace(
                model_ref=lineage.runtime_model_ref,
            ))
            service.observe_production_regression(
                record, SimpleNamespace(run_record=run),
            )
            self.assertIsNone(catalog.get(lineage.runtime_model_ref))
            self.assertFalse(state_store.load().packages[0].enabled)
            self.assertEqual(1, len(service.receipts()))
            self.assertEqual(
                "forced_regression_rollback",
                service.receipts()[0].action.value,
            )

    def test_missing_retirement_confirmation_changes_nothing(self):
        service = ProductFactoryLifecycle(
            repositories=object(), lifecycle=object(),
            catalog=RuntimeModelCatalog(()), installer=_Installer(),
            artifact_root=Path("/tmp"), workspace_root=Path("/tmp"),
        )
        with self.assertRaisesRegex(PermissionError, "confirmation"):
            service.retire(
                request_id="retire-specialist-1", release_id="release-1",
                expected_lifecycle_revision=1, reason_code="owner-request",
                remove_artifact=False, confirmed=False,
            )


if __name__ == "__main__":
    unittest.main()
