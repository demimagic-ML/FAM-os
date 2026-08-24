from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fam_os.adapters.ollama.canary_installer import OllamaCanaryModelInstaller


class OllamaCanaryModelInstallerTests(unittest.TestCase):
    def test_create_uses_stable_show_api_and_hashes_canonical_manifest(self) -> None:
        transport = _Transport({
            ("POST", "http://local/api/show"): {
                "details": {"format": "gguf"}, "parameters": "temperature 0",
            },
        })
        installer = OllamaCanaryModelInstaller(
            Path("/usr/bin/ollama"), "http://local/", transport=transport,
        )
        manifest = {"details": {"format": "gguf"}, "parameters": "temperature 0"}
        with patch(
            "fam_os.adapters.ollama.canary_installer.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ) as run:
            digest = installer.create("specialist:test", Path(__file__))

        expected = hashlib.sha256(json.dumps(
            manifest, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        self.assertEqual(expected, digest)
        self.assertEqual(
            ("POST", "http://local/api/show", {
                "model": "specialist:test", "verbose": False,
            }, 60),
            transport.calls[0],
        )
        self.assertNotIn("show", run.call_args.args[0])

    def test_remove_uses_catalog_api_and_confirms_absence(self) -> None:
        transport = _SequencedTransport((
            {"models": [{"name": "specialist:test"}]},
            {"models": []},
        ))
        installer = OllamaCanaryModelInstaller(
            Path("/usr/bin/ollama"), "http://local", transport=transport,
        )
        with patch(
            "fam_os.adapters.ollama.canary_installer.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ) as run:
            installer.remove("specialist:test")

        self.assertEqual(("/usr/bin/ollama", "rm", "specialist:test"), run.call_args.args[0])
        self.assertEqual(2, len(transport.calls))
        self.assertTrue(all(call[:2] == ("GET", "http://local/api/tags") for call in transport.calls))

    def test_remove_does_not_call_cli_when_model_is_absent(self) -> None:
        installer = OllamaCanaryModelInstaller(
            Path("/usr/bin/ollama"), "http://local",
            transport=_SequencedTransport(({"models": []},)),
        )
        with patch(
            "fam_os.adapters.ollama.canary_installer.subprocess.run",
        ) as run:
            installer.remove("specialist:missing")
        run.assert_not_called()

    def test_create_removes_imported_model_when_manifest_validation_fails(self) -> None:
        transport = _FailingShowTransport()
        installer = OllamaCanaryModelInstaller(
            Path("/usr/bin/ollama"), "http://local", transport=transport,
        )
        with patch(
            "fam_os.adapters.ollama.canary_installer.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "show failed"):
                installer.create("specialist:test", Path(__file__))

        self.assertEqual(2, run.call_count)
        self.assertEqual(
            ("/usr/bin/ollama", "rm", "specialist:test"),
            run.call_args.args[0],
        )


class _Transport:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def request(self, method, url, payload, timeout_seconds):
        self.calls.append((method, url, payload, timeout_seconds))
        return self.responses[(method, url)]


class _SequencedTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, payload, timeout_seconds):
        self.calls.append((method, url, payload, timeout_seconds))
        return next(self.responses)


class _FailingShowTransport:
    def __init__(self):
        self.catalogs = iter((
            {"models": [{"name": "specialist:test"}]},
            {"models": []},
        ))

    def request(self, method, url, payload, timeout_seconds):
        if url.endswith("/api/show"):
            raise RuntimeError("show failed")
        return next(self.catalogs)


if __name__ == "__main__":
    unittest.main()
