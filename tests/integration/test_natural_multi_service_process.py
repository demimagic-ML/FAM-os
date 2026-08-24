import hashlib
import socket
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.engineering_recipes import (
    Ed25519RecipeSignatureVerifier,
    sign_recipe_specification,
)
from fam_os.adapters.integration import (
    NaturalIntegrationEnvironmentPlanner,
    ProcessIntegrationEnvironmentAdapter,
)
from fam_os.core.engineering import (
    CandidateBaselineEntry,
    CandidateEntryKind,
    CandidateWorkspace,
    EngineeringEcosystem,
    IntegrationEnvironmentStatus,
    IntegrationExecutionPermit,
    NaturalLanguageEngineeringPlanner, ToolRecipePurpose,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.production_recipes import ToolRecipeSpecification


class NaturalMultiServiceProcessTests(unittest.TestCase):
    def test_signed_api_and_static_templates_run_health_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            candidate_root = root / "candidate"
            candidate_root.mkdir()
            api = candidate_root / "api.py"
            api.write_text(_API_SERVER, encoding="utf-8")
            html = candidate_root / "index.html"
            html.write_text("<h1>Natural full stack</h1>\n", encoding="utf-8")
            instant = datetime.now(timezone.utc)
            candidate = CandidateWorkspace(
                "candidate-natural-multi", "task-natural-multi", "baseline-1",
                str(root / "owner"), str(candidate_root), instant, "copy",
                "a" * 64,
                (
                    _entry("api.py", api),
                    _entry("index.html", html),
                ),
            )
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=(
                    "Update the API and page, then run the full-stack app "
                    "end-to-end before applying."
                ),
                workspace_root=str(root / "owner"), owner_id="owner-1",
                principal_id="owner-1", task_id="task-natural-multi",
                grant_id="grant-natural-multi", toolchains=("python", "html"),
                now=instant,
            )
            ports = _free_ports(2)
            plan = NaturalIntegrationEnvironmentPlanner("host-local").build(
                proposal.definition, candidate, ("api.py", "index.html"),
                "changeset-natural-multi", ports, postapply=False, now=instant,
            )
            permit = IntegrationExecutionPermit(
                "permit-natural-multi", plan.environment_id,
                plan.approved_changeset_id, plan.exact_host_id, ("decision-1",),
                instant, instant + timedelta(minutes=5),
            )
            adapter = ProcessIntegrationEnvironmentAdapter(_catalog())

            ready = adapter.launch(plan, candidate_root, permit, _Control())
            try:
                self.assertEqual(IntegrationEnvironmentStatus.READY, ready.status)
                self.assertEqual(
                    ("python-api-candidate", "static-preview-candidate"),
                    tuple(item.service_id for item in ready.services),
                )
                self.assertTrue(all(item.health_evidence_id for item in ready.services))
            finally:
                cleaned = adapter.cleanup(plan, ready, candidate_root, permit)
            self.assertEqual(IntegrationEnvironmentStatus.CLEANED, cleaned.status)
            self.assertEqual(2, len(cleaned.cleanup_evidence_ids))


class _Control:
    @staticmethod
    def cancelled():
        return False

    @staticmethod
    def authorization_active():
        return True


def _entry(relative: str, path: Path) -> CandidateBaselineEntry:
    content = path.read_bytes()
    return CandidateBaselineEntry(
        relative, CandidateEntryKind.FILE,
        hashlib.sha256(content).hexdigest(), len(content), False,
    )


def _catalog() -> SignedToolRecipeCatalog:
    key = Ed25519PrivateKey.generate()
    catalog = SignedToolRecipeCatalog(
        Ed25519RecipeSignatureVerifier({"release": key.public_key()}),
    )
    for specification in (
        ToolRecipeSpecification(
            EngineeringEcosystem.PYTHON, ToolRecipePurpose.ACCEPTANCE,
            "/usr/bin/python3", ("/workspace/api.py", "{port:api}"),
            "integration.root-api.health.v1", "integration.python.root-api",
        ),
        ToolRecipeSpecification(
            EngineeringEcosystem.PYTHON, ToolRecipePurpose.ACCEPTANCE,
            "/usr/bin/python3",
            (
                "-m", "http.server", "{port:preview}", "--bind",
                "127.0.0.1", "--directory", "/workspace",
            ),
            "integration.static-http.health.v1",
            "integration.python.static-http",
        ),
    ):
        catalog.admit(sign_recipe_specification(specification, "release", key))
    return catalog


def _free_ports(count: int) -> tuple[int, ...]:
    sockets = []
    try:
        for _item in range(count):
            stream = socket.socket()
            stream.bind(("127.0.0.1", 0))
            sockets.append(stream)
        return tuple(stream.getsockname()[1] for stream in sockets)
    finally:
        for stream in sockets:
            stream.close()


_API_SERVER = """\
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"healthy")
    def log_message(self, *args):
        pass

HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
"""


if __name__ == "__main__":
    unittest.main()
