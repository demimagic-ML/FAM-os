import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fam_os.core.production.model_selection import HostCapacity
from fam_os.product.composition.console_state import ProductConsoleProvider


class _Capacity:
    def observe(self):
        return HostCapacity(
            available_host_bytes=12 * 1024**3,
            available_vram_bytes=8 * 1024**3,
            reserved_host_bytes=2 * 1024**3,
            reserved_vram_bytes=1024**3,
        )


class _Catalog:
    def entries(self):
        return (
            SimpleNamespace(model_ref="small:model"),
            SimpleNamespace(model_ref="strong:model"),
        )

    def provenances(self):
        return (SimpleNamespace(model_ref="small:model"),)


class _Residency:
    def __init__(self):
        self.models = ()

    def resident_models(self):
        return self.models


class _Permissions:
    def __init__(self):
        self.count = 0

    def active_count(self, _instant):
        return self.count


class _Terminals:
    def __init__(self):
        self.count = 0

    def result_count(self):
        return self.count


class _Documents:
    def __init__(self):
        self.values = []

    def list(self):
        return list(self.values)


class _Audit:
    def __init__(self):
        self.count = 0

    def verify(self):
        return SimpleNamespace(
            passed=True, record_count=self.count, head_digest="a" * 64,
            reason_code=None,
        )


class ProductConsoleProviderTests(unittest.TestCase):
    def test_snapshot_reads_current_providers_on_every_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            residency = _Residency()
            permissions = _Permissions()
            terminals = _Terminals()
            documents = _Documents()
            audit = _Audit()
            provider = ProductConsoleProvider(
                Path(temporary), "release-1",
                storage=SimpleNamespace(recovery_required=False, reason="ready"),
                capacity=_Capacity(), catalog=_Catalog(), residency=residency,
                repositories=SimpleNamespace(
                    application_permissions=permissions,
                    terminal_outcomes=terminals,
                ),
                document_indexes=documents, session_memory=object(),
                application_audit=audit,
            )
            first = _items(provider.snapshot())
            self.assertEqual("0", first[("experts", "resident")].value)
            self.assertEqual("0", first[("permissions", "application-grants")].value)
            self.assertEqual("0", first[("memory", "indexes")].value)
            self.assertEqual("0", first[("audit", "terminal-results")].value)

            residency.models = ("strong:model",)
            permissions.count = 2
            documents.values.append({"grant_id": "grant-1"})
            terminals.count = 3
            audit.count = 4
            second = _items(provider.snapshot())
            self.assertEqual("1", second[("experts", "resident")].value)
            self.assertIn("strong:model", second[("experts", "resident")].detail)
            self.assertEqual("2", second[("permissions", "application-grants")].value)
            self.assertEqual("1", second[("memory", "indexes")].value)
            self.assertEqual("3", second[("audit", "terminal-results")].value)
            self.assertEqual("4", second[("audit", "application-actions")].value)

    def test_provider_failure_is_visible_and_does_not_break_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            provider = ProductConsoleProvider(
                Path(temporary), "release-1",
                storage=SimpleNamespace(
                    recovery_required=True, reason="owner key unavailable",
                ),
            )
            snapshot = provider.snapshot()
            items = _items(snapshot)
            self.assertTrue(snapshot.recovery_mode)
            self.assertEqual("Enabled", items[("recovery", "mode")].value)
            for section in ("resources", "experts", "permissions", "audit"):
                self.assertEqual("unavailable", items[(section, "state")].status)


def _items(snapshot):
    return {
        (section.section_id, item.item_id): item
        for section in snapshot.sections
        for item in section.items
    }


if __name__ == "__main__":
    unittest.main()
