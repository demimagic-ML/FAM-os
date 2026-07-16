import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.filesystem import JsonExpertResidencyRepository
from fam_os.scheduler import ExpertResidencyIdentity, initial_cold_residency_catalog
from fam_os.scheduler.residency_ports import ResidencyRevisionConflict


NOW = datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc)


def catalog():
    return initial_cold_residency_catalog(
        "catalog-1", (ExpertResidencyIdentity("expert.qwen", "qwen:7b"),), NOW
    )


class JsonExpertResidencyRepositoryTests(unittest.TestCase):
    def test_private_atomic_state_survives_new_repository_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            repository = JsonExpertResidencyRepository(path)
            initial = repository.initialize(catalog())
            updated = replace(initial, revision=1)
            repository.compare_and_swap(0, updated)

            self.assertEqual(JsonExpertResidencyRepository(path).read(), updated)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_compare_and_swap_rejects_stale_or_skipped_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = JsonExpertResidencyRepository(Path(directory) / "state.json")
            initial = repository.initialize(catalog())
            with self.assertRaisesRegex(ResidencyRevisionConflict, "replacement"):
                repository.compare_and_swap(0, replace(initial, revision=2))
            repository.compare_and_swap(0, replace(initial, revision=1))
            with self.assertRaisesRegex(ResidencyRevisionConflict, "conflict"):
                repository.compare_and_swap(0, replace(initial, revision=1))

    def test_state_and_lock_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text("not state")
            path = root / "state.json"
            path.symlink_to(target)
            with self.assertRaises(ResidencyRevisionConflict):
                JsonExpertResidencyRepository(path).read()

            path.unlink()
            lock = root / "state.json.lock"
            lock.unlink()
            lock.symlink_to(target)
            with self.assertRaises(OSError):
                JsonExpertResidencyRepository(path).initialize(catalog())

    def test_relative_state_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            JsonExpertResidencyRepository(Path("state.json"))

    def test_broad_state_permissions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            repository = JsonExpertResidencyRepository(path)
            repository.initialize(catalog())
            path.chmod(0o644)
            with self.assertRaisesRegex(ResidencyRevisionConflict, "permissions"):
                repository.read()


if __name__ == "__main__":
    unittest.main()
