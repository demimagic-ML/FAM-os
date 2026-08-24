import json
import http.cookiejar
import tempfile
import time
import unittest
import urllib.request
import urllib.error
import stat
import hashlib
from pathlib import Path

from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.core.ports.inference import LoadedModel
from fam_os.scheduler import (
    ContextMemoryModelProfile,
    ContextMemoryStrategy,
    ContextProfileSource,
)
from fam_os.telemetry import InferenceMetrics
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.product.storage.terminal_redaction import TERMINAL_CONTENT_REDACTION
from fam_os.memory import DocumentCorrectionRequest, DocumentDeletionRequest
from fam_os.shell import ShellAskCommand, ShellMemoryOperation, ShellMemoryQuery


class _Response:
    content = "Operational local response"
    metrics = InferenceMetrics("qwen2.5-coder:7b", .01, 0, 1, 3, 300)


class _Runtime:
    def __init__(self):
        self.prompts = []
        self.messages = []
        self.models = {}

    def chat(self, request):
        self.prompts.append(request.messages[-1].content)
        self.messages.append(tuple(item.content for item in request.messages))
        return _Response()

    def unload(self, model_ref):
        self.models.pop(model_ref, None)

    def prewarm(self, model_ref, keep_alive="10m"):
        self.models[model_ref] = LoadedModel(
            model_ref, 1024**3, 0, 8_192,
        )

    def prewarm_embedding(self, model_ref, keep_alive="10m"):
        self.prewarm(model_ref, keep_alive)

    def loaded_models(self):
        return tuple(self.models[key] for key in sorted(self.models))

    def embed(self, request):
        return EmbeddingResponse(
            request.model_ref,
            tuple((float(len(value)), 1.0) for value in request.inputs),
            len(request.inputs), 0.01,
        )


class _Profiles:
    def observe(self, policy):
        encoder = policy.strategy is ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND
        return ContextMemoryModelProfile(
            policy.profile_id, policy.expert_id, policy.model_ref, "test",
            policy.strategy, policy.declared_maximum_context_tokens,
            2, 64, 4,
            None if encoder else 2,
            None if encoder else 16,
            None if encoder else 16,
            2, 1_000, 100, 0,
            ContextProfileSource.OBSERVED_METADATA,
            ("test.profile",),
        )


class ProductServiceTests(unittest.TestCase):
    def test_console_opt_in_index_persists_encrypted_across_service_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            models = _model_root(root / "source-models")
            documents = root / "documents"
            documents.mkdir()
            (documents / "README.md").write_text(
                "PHASE20_SERVICE_NONCE project identity", encoding="utf-8",
            )
            settings = ProductServiceSettings(
                root / "state", root / "runtime", console_port=0,
                source_model_root=models,
            )
            service = LocalProductService(
                settings, _Runtime(), context_profile_observer=_Profiles(),
            )
            service.start()
            try:
                self.assertIsNotNone(service.document_indexes)
                token = (root / "runtime" / "console.token").read_text().strip()
                base = f"http://127.0.0.1:{service.console_server.server_port}"
                opener, csrf = _console_session(base, token)
                request = urllib.request.Request(
                    base + "/api/v1/memory/indexes",
                    data=json.dumps({
                        "path": str(documents), "kind": "folder", "recursive": True,
                        "allowed_extensions": [".md"], "expires_in_hours": 24,
                        "workspace_ids": ["project"], "confirmed": True,
                    }).encode(),
                    method="POST",
                    headers={
                        "Content-Type": "application/json", "Origin": base,
                        "X-CSRF-Token": csrf,
                    },
                )
                receipt = json.loads(opener.open(request).read())
                self.assertTrue(receipt["passed"])
                document_id = receipt["indexed_document_ids"][0]
                shell = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime" / "shell.sock", 5,
                ))
                listed = shell.memory_query(ShellMemoryQuery(
                    "memory-list", ShellMemoryOperation.LIST,
                ))
                self.assertEqual(document_id, listed.documents[0].approval.document_id)
                inspected = shell.memory_query(ShellMemoryQuery(
                    "memory-inspect", ShellMemoryOperation.INSPECT,
                    document_id, limit=1,
                )).documents[0]
                exported = shell.memory_query(ShellMemoryQuery(
                    "memory-export", ShellMemoryOperation.EXPORT,
                    document_id, limit=1,
                )).exported_document
                self.assertIn("PHASE20_SERVICE_NONCE", exported.content)
                corrected_content = "PHASE20_CORRECTED_NONCE project identity"
                corrected_digest = hashlib.sha256(corrected_content.encode()).hexdigest()
                shell.memory_correct(DocumentCorrectionRequest(
                    "memory-correct", document_id, inspected.content_sha256,
                    corrected_content, corrected_digest, True,
                ))
            finally:
                service.stop()

            self.assertNotIn(
                b"PHASE20_SERVICE_NONCE",
                (root / "state/state/fam.sqlite3").read_bytes(),
            )
            self.assertNotIn(
                b"PHASE20_CORRECTED_NONCE",
                (root / "state/state/fam.sqlite3").read_bytes(),
            )
            restarted = LocalProductService(
                settings, _Runtime(), context_profile_observer=_Profiles(),
            )
            restarted.start()
            try:
                token = (root / "runtime" / "console.token").read_text().strip()
                base = f"http://127.0.0.1:{restarted.console_server.server_port}"
                opener, _csrf = _console_session(base, token)
                indexes = json.loads(
                    opener.open(base + "/api/v1/memory/indexes").read(),
                )["indexes"]
                self.assertEqual(1, len(indexes))
                self.assertEqual(str(documents), indexes[0]["root_path"])
                shell = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime" / "shell.sock", 5,
                ))
                exported = shell.memory_query(ShellMemoryQuery(
                    "memory-export-restart", ShellMemoryOperation.EXPORT,
                    document_id, limit=1,
                )).exported_document
                self.assertEqual(corrected_content, exported.content)
                history = shell.memory_query(ShellMemoryQuery(
                    "memory-receipts", ShellMemoryOperation.RECEIPTS,
                ))
                self.assertEqual("correct", history.receipts[0].operation.value)
                shell.memory_delete(DocumentDeletionRequest(
                    "memory-delete", document_id, corrected_digest, True,
                ))
                remaining = shell.memory_query(ShellMemoryQuery(
                    "memory-list-after-delete", ShellMemoryOperation.LIST,
                ))
                self.assertEqual(0, remaining.total_count)
            finally:
                restarted.stop()

    def test_one_service_answers_shell_and_console_then_stops(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(
                ProductServiceSettings(root / "state", root / "runtime", console_port=0),
                _Runtime(),
                context_profile_observer=_Profiles(),
            )
            service.start()
            try:
                application_socket = root / "runtime" / "applications.sock"
                mode = application_socket.stat().st_mode
                self.assertTrue(stat.S_ISSOCK(mode))
                self.assertEqual(stat.S_IMODE(mode), 0o600)
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime" / "shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand("request", "hello"))
                deadline = time.monotonic() + 3
                while True:
                    result = client.snapshot(accepted.session_id)
                    if result.result is not None or time.monotonic() >= deadline:
                        break
                    time.sleep(0.01)
                self.assertIsNotNone(result.result)
                self.assertEqual(result.result.content, "Operational local response")
                repositories = service._storage_unit.core.repositories()
                self.assertEqual(
                    TERMINAL_CONTENT_REDACTION,
                    repositories.requests.get("request").prompt,
                )
                self.assertEqual((), service.outcome_learning.records())
                token = (root / "runtime" / "console.token").read_text().strip()
                port = service.console_server.server_port
                base = f"http://127.0.0.1:{port}"
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
                )
                exchange = urllib.request.Request(
                    base + "/api/v1/session", data=b"{}", method="POST",
                    headers={"Authorization": f"Bearer {token}", "Origin": base},
                )
                opener.open(exchange).read()
                payload = json.loads(opener.open(base + "/api/v1/snapshot").read())
                self.assertEqual(len(payload["sections"]), 6)
            finally:
                service.stop()
            self.assertFalse((root / "runtime" / "shell.sock").exists())
            self.assertFalse((root / "runtime" / "applications.sock").exists())

    def test_console_session_memory_is_composed_and_cookie_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = _Runtime()
            service = LocalProductService(
                ProductServiceSettings(root / "state", root / "runtime", console_port=0),
                runtime,
                context_profile_observer=_Profiles(),
            )
            service.start()
            try:
                token = (root / "runtime" / "console.token").read_text().strip()
                base = f"http://127.0.0.1:{service.console_server.server_port}"
                first_opener, first_csrf = _console_session(base, token)
                _run_task(
                    first_opener, base, first_csrf, "memory-1",
                    "My private codename is ORBIT.",
                )
                _run_task(
                    first_opener, base, first_csrf, "memory-2",
                    "What is my private codename?",
                )
                second_opener, second_csrf = _console_session(base, token)
                _run_task(
                    second_opener, base, second_csrf, "memory-3",
                    "What is another session's codename?",
                )
                self.assertEqual("What is my private codename?", runtime.prompts[1])
                self.assertIn(
                    "user: My private codename is ORBIT.", runtime.messages[1][1],
                )
                self.assertNotIn("My private codename is ORBIT.", runtime.prompts[2])
            finally:
                service.stop()


def _console_session(base: str, token: str):
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    exchange = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": f"Bearer {token}", "Origin": base},
    )
    document = json.loads(opener.open(exchange).read())
    return opener, document["csrf_token"]


def _run_task(opener, base: str, csrf: str, request_id: str, prompt: str) -> dict:
    request = urllib.request.Request(
        base + "/api/v1/tasks",
        data=json.dumps({"request_id": request_id, "prompt": prompt}).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json", "Origin": base,
            "X-CSRF-Token": csrf,
        },
    )
    try:
        task = json.loads(opener.open(request).read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise AssertionError(f"Console task creation failed: {error.code} {detail}") from error
    deadline = time.monotonic() + 3
    while task.get("result") is None and time.monotonic() < deadline:
        time.sleep(0.01)
        task = json.loads(opener.open(
            base + f"/api/v1/tasks/{task['session_id']}",
        ).read())
    if task.get("result") is None:
        raise AssertionError("Console task did not finish")
    return task


def _model_root(root: Path) -> Path:
    digest = hashlib.sha256(b"model").hexdigest()
    blob = root / "blobs" / f"sha256-{digest}"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"model")
    manifest = json.dumps({
        "config": {"digest": f"sha256:{digest}"}, "layers": [],
    })
    for model in ("qwen3", "nomic-embed-text"):
        path = root / "manifests/registry.ollama.ai/library" / model / (
            "1.7b" if model == "qwen3" else "latest"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(manifest, encoding="utf-8")
    return root


if __name__ == "__main__":
    unittest.main()
