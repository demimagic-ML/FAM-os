import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider


class ConsoleNaturalEngineeringTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.api = _Api()
        self.server = ConsoleHttpServer(
            ("127.0.0.1", 0), LocalConsoleProvider(Path(self.temporary.name)),
            "x" * 32, natural_engineering_api=self.api,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def test_prompt_proposal_and_exact_confirmation_use_same_console_session(self):
        opener, csrf = _session(self.base)
        proposed = _post(
            opener, self.base + "/api/v1/engineering/natural-language/proposals",
            csrf, {
                "prompt": "Implement and test it", "workspace_root": "/workspace/project",
                "authority_profile": "workspace",
            },
        )
        resources = _post(
            opener,
            self.base + "/api/v1/engineering/natural-language/proposals/"
            + proposed["proposal_id"] + "/integration-resource-decision",
            csrf, {"confirmed": True},
        )
        activated = _post(
            opener,
            self.base + "/api/v1/engineering/natural-language/proposals/"
            + proposed["proposal_id"] + "/activate",
            csrf, {"confirmed": True},
        )
        progress = _get(
            opener,
            self.base + "/api/v1/engineering/natural-language/proposals/"
            + proposed["proposal_id"] + "/progress",
        )
        completed = _post(
            opener,
            self.base + "/api/v1/engineering/natural-language/proposals/"
            + proposed["proposal_id"] + "/changeset-decision",
            csrf, {"changeset_id": "changeset-1", "confirmed": True},
        )
        waived = _post(
            opener,
            self.base + "/api/v1/engineering/natural-language/proposals/"
            + proposed["proposal_id"] + "/review-waiver",
            csrf, {
                "checkpoint_id": "review-1", "finding_id": "finding-1",
                "consequences_sha256": "a" * 64, "confirmed": True,
            },
        )
        published = _post(
            opener,
            self.base + "/api/v1/engineering/natural-language/proposals/"
            + proposed["proposal_id"] + "/publication-decision",
            csrf, {
                "publication_proposal_id": "publication-1", "confirmed": True,
            },
        )
        rolled_back = _post(
            opener,
            self.base + "/api/v1/engineering/natural-language/proposals/"
            + proposed["proposal_id"] + "/rollback",
            csrf, {"rollback_id": "rollback-changeset-1", "confirmed": True},
        )

        self.assertEqual("proposal-1", proposed["proposal_id"])
        self.assertEqual("approved", resources["proposal"]["resource_status"])
        self.assertEqual("candidate_ready", activated["engineering_task"]["stage"])
        self.assertEqual("candidate_ready", progress["engineering_task"]["stage"])
        self.assertEqual("reverified", completed["engineering_task"]["stage"])
        self.assertEqual("changeset_approval_required", waived["engineering_task"]["outcome"])
        self.assertEqual("completed", published["engineering_task"]["stage"])
        self.assertEqual("rolled_back", rolled_back["engineering_task"]["stage"])
        self.assertTrue(self.api.activation_session_id)
        self.assertEqual(self.api.proposal_session_id, self.api.activation_session_id)
        self.assertEqual(self.api.activation_session_id, self.api.decision_session_id)
        self.assertEqual(self.api.activation_session_id, self.api.rollback_session_id)
        self.assertEqual(self.api.activation_session_id, self.api.publication_session_id)
        self.assertEqual(self.api.activation_session_id, self.api.review_session_id)
        self.assertEqual(self.api.activation_session_id, self.api.resource_session_id)


class _Api:
    owner_id = "owner-1"

    def __init__(self):
        self.activation_session_id = None
        self.decision_session_id = None
        self.rollback_session_id = None
        self.publication_session_id = None
        self.review_session_id = None
        self.resource_session_id = None
        self.proposal_session_id = None

    def propose(
        self, owner_id, prompt, workspace_root, *, transport_session_id=None,
        authority_profile=None,
    ):
        self.proposal_session_id = transport_session_id
        self.authority_profile = authority_profile
        return {"proposal_id": "proposal-1", "status": "proposed"}

    def activate(self, owner_id, proposal_id, session_id, confirmed):
        self.activation_session_id = session_id
        return {
            "proposal": {"proposal_id": proposal_id, "status": "activated"},
            "engineering_task": {"task_id": "task-1", "stage": "candidate_ready"},
        }

    def approve_integration_resources(
        self, owner_id, proposal_id, session_id, confirmed,
    ):
        self.resource_session_id = session_id
        return {
            "proposal": {
                "proposal_id": proposal_id, "status": "proposed",
                "resource_status": "approved",
            },
            "engineering_task": None,
        }

    def progress(self, owner_id, proposal_id):
        return {
            "proposal": {"proposal_id": proposal_id, "status": "activated"},
            "engineering_task": {"task_id": "task-1", "stage": "candidate_ready"},
        }

    def approve_changeset(
        self, owner_id, proposal_id, changeset_id, session_id, confirmed,
    ):
        self.decision_session_id = session_id
        return {
            "proposal": {"proposal_id": proposal_id, "status": "activated"},
            "engineering_task": {
                "task_id": "task-1", "stage": "reverified",
                "outcome": "reverification_completed",
            },
        }

    def rollback(
        self, owner_id, proposal_id, rollback_id, session_id, confirmed,
    ):
        self.rollback_session_id = session_id
        return {
            "proposal": {"proposal_id": proposal_id, "status": "activated"},
            "engineering_task": {
                "task_id": "task-1", "stage": "rolled_back",
                "outcome": "rollback_completed",
            },
        }

    def waive_review(
        self, owner_id, proposal_id, checkpoint_id, finding_id,
        consequences_sha256, session_id, confirmed,
    ):
        self.review_session_id = session_id
        return {
            "proposal": {"proposal_id": proposal_id, "status": "activated"},
            "engineering_task": {
                "task_id": "task-1", "stage": "changeset_approval_required",
                "outcome": "changeset_approval_required",
            },
        }

    def approve_publication(
        self, owner_id, proposal_id, publication_id, session_id, confirmed,
    ):
        self.publication_session_id = session_id
        return {
            "proposal": {"proposal_id": proposal_id, "status": "activated"},
            "engineering_task": {
                "task_id": "task-1", "stage": "completed",
                "outcome": "publication_completed",
            },
        }


def _session(base):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    request = urllib.request.Request(
        base + "/api/v1/session", data=b"{}", method="POST",
        headers={"Authorization": "Bearer " + "x" * 32, "Origin": base},
    )
    with opener.open(request) as response:
        document = json.load(response)
    return opener, document["csrf_token"]


def _post(opener, url, csrf, document):
    request = urllib.request.Request(
        url, data=json.dumps(document).encode(), method="POST",
        headers={
            "Content-Type": "application/json", "X-CSRF-Token": csrf,
            "Origin": url.split("/api/", 1)[0],
        },
    )
    with opener.open(request) as response:
        return json.load(response)


def _get(opener, url):
    with opener.open(url) as response:
        return json.load(response)


if __name__ == "__main__":
    unittest.main()
