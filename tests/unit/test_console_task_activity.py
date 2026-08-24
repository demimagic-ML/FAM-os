import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from fam_os.applications import ObservationResult, ObservationStatus
from fam_os.console.task_activity import task_activity_document


class ConsoleTaskActivityTests(unittest.TestCase):
    def test_real_observation_payload_is_projected_as_tool_evidence(self):
        observed = ObservationResult(
            "observation-1", ObservationStatus.OBSERVED, datetime.now(UTC),
            {
                "path": "/home/owner/project",
                "entries": [{"name": "README.md", "kind": "file"}],
                "truncated": False,
            },
            "file:///home/owner/project/", "directory:1:2:3",
        )
        record = SimpleNamespace(
            application_instance_id="owner-filesystem",
            resource_uri="file:///home/owner/project/",
            permission_grant_id="grant-1",
            observations=(observed,), proposal=None, confirmation=None,
            action_result=None,
        )

        document = task_activity_document(record)

        self.assertTrue(document["available"])
        self.assertEqual("os.directory.list", document["items"][0]["capability_id"])
        self.assertEqual("README.md", document["items"][0]["output"]["entries"][0]["name"])
        self.assertEqual("observation-1", document["items"][0]["receipt_id"])


if __name__ == "__main__":
    unittest.main()
