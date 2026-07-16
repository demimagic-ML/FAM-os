import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fam_os.experts import ExpertTier, LocalExpertRegistry
from tests.unit.test_package_expert_manifests import _manifest, _package


NOW = datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc)


def manifest(name: str, version: str = "1.0.0", **overrides):
    values = {
        "package": _package(package_id=f"package.{name}", package_version=version),
        "expert_id": f"expert.{name}",
    }
    values.update(overrides)
    return _manifest(**values)


class LocalExpertRegistryTests(unittest.TestCase):
    def test_refresh_indexes_coordinates_experts_capabilities_and_publishers(self):
        registry = self.registry()
        code = manifest("code")
        language = manifest(
            "language", capabilities=("language.summarize",), tier=ExpertTier.MICRO
        )
        self.assertTrue(registry.refresh((language, code)))

        self.assertEqual(code, registry.lookup("package.code", "1.0.0"))
        self.assertEqual((code,), registry.versions("expert.code"))
        self.assertEqual((language,), registry.find_by_capability("language.summarize"))
        self.assertEqual((code, language), registry.find_by_publisher("fam-project"))
        self.assertEqual(1, registry.snapshot().revision)

    def test_multiple_versions_are_discoverable_without_selecting_an_active_one(self):
        registry = self.registry()
        old = manifest("code", "1.0.0")
        new = manifest("code", "2.0.0")
        registry.refresh((new, old))
        self.assertEqual((old, new), registry.versions("expert.code"))

    def test_exact_capability_and_tier_filters_do_not_expand_hierarchy(self):
        registry = self.registry()
        broad = manifest("broad", capabilities=("code",), tier=ExpertTier.MICRO)
        exact = manifest("exact", capabilities=("code.generate.python",))
        registry.refresh((broad, exact))
        self.assertEqual((exact,), registry.find_by_capability("code.generate.python"))
        self.assertEqual((broad,), registry.find_by_capability("code", ExpertTier.MICRO))

    def test_identical_refresh_is_idempotent_and_event_is_revisioned(self):
        registry = self.registry()
        value = manifest("code")
        self.assertTrue(registry.refresh((value,)))
        self.assertFalse(registry.refresh((value,)))
        self.assertEqual(1, registry.snapshot().revision)
        self.assertEqual((1,), tuple(event.revision for event in registry.events()))

    def test_duplicate_coordinate_and_in_place_content_change_are_rejected_atomically(self):
        registry = self.registry()
        original = manifest("code")
        registry.refresh((original,))
        before = registry.snapshot()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            registry.refresh((original, original))
        changed = manifest("code", display_name="Changed without version")
        with self.assertRaisesRegex(ValueError, "without a new version"):
            registry.refresh((changed,))
        self.assertEqual(before, registry.snapshot())

    def test_event_failure_and_concurrent_refresh_never_partially_mutate(self):
        broken = LocalExpertRegistry(
            clock=lambda: NOW,
            event_id_factory=lambda: (_ for _ in ()).throw(RuntimeError("event failed")),
        )
        with self.assertRaisesRegex(RuntimeError, "event failed"):
            broken.refresh((manifest("code"),))
        self.assertEqual(0, broken.snapshot().revision)

        registry = LocalExpertRegistry()
        catalogs = tuple((manifest(f"code-{index}"),) for index in range(12))
        with ThreadPoolExecutor(max_workers=6) as executor:
            tuple(executor.map(registry.refresh, catalogs))
        self.assertEqual(12, registry.snapshot().revision)
        self.assertEqual(1, len(registry.snapshot().manifests))

    def registry(self):
        ids = iter(range(20))
        return LocalExpertRegistry(
            clock=lambda: NOW,
            event_id_factory=lambda: f"expert-event-{next(ids)}",
        )


if __name__ == "__main__":
    unittest.main()
