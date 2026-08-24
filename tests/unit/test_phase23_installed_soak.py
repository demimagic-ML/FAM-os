import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.phase23_installed_matrix.service import CandidateService
from tools.phase23_soak.contracts import REQUIRED_EVENT_MINIMUMS, SoakSettings
from tools.phase23_soak.evidence import EvidenceLedger
from tools.phase23_soak.low_disk import _integer_fact, _namespace_prefix


class Phase23InstalledSoakTests(unittest.TestCase):
    def test_ledger_accepts_the_orchestrator_created_private_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = self._settings(root, duration=60, full=False)
            output = root / "output"
            output.mkdir(mode=0o700)
            ledger = EvidenceLedger(output, settings)
        self.assertEqual(output / "events.jsonl", ledger.events_path)

    def test_short_run_can_pass_preflight_but_not_qualification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = self._settings(root, duration=60, full=False)
            ledger = EvidenceLedger(root / "output", settings)
            self._required_events(ledger)
            report = ledger.finalize(
                started_at="2026-07-18T00:00:00+00:00",
                duration_seconds=60,
                candidate={"release_id": "candidate"},
                cleanup=self._cleanup(),
            )
        self.assertTrue(report["preflight_passed"])
        self.assertFalse(report["qualification_eligible"])
        self.assertFalse(report["qualification_passed"])
        self.assertFalse(report["passed"])

    def test_full_duration_and_every_real_event_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = self._settings(root, duration=86_400, full=True)
            ledger = EvidenceLedger(root / "output", settings)
            self._required_events(ledger)
            report = ledger.finalize(
                started_at="2026-07-18T00:00:00+00:00",
                duration_seconds=86_400,
                candidate={"release_id": "candidate"},
                cleanup=self._cleanup(),
            )
        self.assertTrue(report["event_chain_valid"])
        self.assertTrue(report["qualification_eligible"])
        self.assertTrue(report["qualification_passed"])

    def test_tampered_append_only_event_chain_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = self._settings(root, duration=86_400, full=True)
            ledger = EvidenceLedger(root / "output", settings)
            self._required_events(ledger)
            lines = ledger.events_path.read_text().splitlines()
            event = json.loads(lines[0])
            event["passed"] = False
            lines[0] = json.dumps(event, sort_keys=True, separators=(",", ":"))
            ledger.events_path.write_text("\n".join(lines) + "\n")
            report = ledger.finalize(
                started_at="2026-07-18T00:00:00+00:00",
                duration_seconds=86_400,
                candidate={}, cleanup=self._cleanup(),
            )
        self.assertFalse(report["event_chain_valid"])
        self.assertFalse(report["preflight_passed"])
        self.assertFalse(report["qualification_passed"])

    def test_candidate_launch_prefix_precedes_installed_python_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            installation = Mock()
            installation.prefix = root / "candidate"
            service = CandidateService(
                installation, root / "state", root / "run",
                ollama_url="http://127.0.0.1:11434",
                source_model_root=root / "models",
                launch_prefix=("unshare", "--mount", "helper.py", "--"),
            )
            process = Mock()
            process.pid = 12345
            process.poll.return_value = None
            try:
                with (
                    patch(
                        "tools.phase23_installed_matrix.service.subprocess.Popen",
                        return_value=process,
                    ) as spawn,
                    patch.object(service, "wait_ready"),
                ):
                    service.start()
                command = spawn.call_args.args[0]
                self.assertEqual(
                    ("unshare", "--mount", "helper.py", "--"),
                    command[:4],
                )
                self.assertEqual("-c", command[5])
                self.assertEqual(process.pid, service.pid)
            finally:
                if service._stdout is not None:
                    service._stdout.close()
                if service._stderr is not None:
                    service._stderr.close()

    def test_settings_reject_existing_output_and_unsafe_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            models = root / "models"
            output = root / "output"
            repository.mkdir()
            models.mkdir()
            output.mkdir()
            with self.assertRaisesRegex(ValueError, "new absolute"):
                SoakSettings(
                    repository, output, "phase23-soak-test",
                    source_model_root=models,
                )
            with self.assertRaisesRegex(ValueError, "identity"):
                SoakSettings(
                    repository, root / "new", "unsafe/id",
                    source_model_root=models,
                )

    def test_low_disk_namespace_is_bounded_and_rejects_weak_facts(self) -> None:
        prefix = _namespace_prefix(
            Path("/target"), Path("/seed"), Path("/export"), Path("/control"),
        )
        self.assertEqual(
            ("unshare", "--user", "--map-root-user", "--mount"), prefix[:4],
        )
        self.assertIn("--size-bytes", prefix)
        self.assertEqual(0, _integer_fact({"free_after_bytes": 0}, "free_after_bytes"))
        with self.assertRaisesRegex(ValueError, "integer"):
            _integer_fact({"free_after_bytes": "0"}, "free_after_bytes")

    @staticmethod
    def _settings(
        root: Path, *, duration: float, full: bool,
    ) -> SoakSettings:
        repository = root / "repository"
        models = root / "models"
        repository.mkdir()
        models.mkdir()
        return SoakSettings(
            repository=repository,
            output_root=root / "declared-output",
            run_id="phase23-soak-test",
            duration_seconds=duration,
            request_interval_seconds=1,
            connector_interval_seconds=1,
            daemon_restart_interval_seconds=1,
            provider_crash_interval_seconds=1,
            source_model_root=models,
            full_model_pressure=full,
        )

    @staticmethod
    def _required_events(ledger: EvidenceLedger) -> None:
        for kind, minimum in REQUIRED_EVENT_MINIMUMS.items():
            for _ in range(minimum):
                ledger.append(kind, True, {"content_free": True})

    @staticmethod
    def _cleanup() -> dict[str, object]:
        return {
            "complete_removal": True,
            "owner_service_preserved": True,
            "managed_ollama_inactive": True,
        }


if __name__ == "__main__":
    unittest.main()
