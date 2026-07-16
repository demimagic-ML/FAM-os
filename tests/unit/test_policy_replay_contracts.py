import unittest
from dataclasses import replace
from datetime import datetime, timezone

from fam_os.scheduler import (
    SchedulerPolicyKind,
    SchedulerPolicyReplayRecord,
    SchedulerPolicyReplayReport,
)


def record(index, kind):
    return SchedulerPolicyReplayRecord(
        f"case-{index}", kind, "policy/v1", "input/v1", "output/v1",
        "a" * 64, str(index) * 64, str(index) * 64, True, False,
    )


class PolicyReplayContractTests(unittest.TestCase):
    def test_report_requires_every_policy_kind(self):
        records = tuple(record(index, kind) for index, kind in enumerate(SchedulerPolicyKind, 1))
        report = SchedulerPolicyReplayReport(
            "report", datetime(2026, 7, 16, tzinfo=timezone.utc), records, True,
        )
        with self.assertRaisesRegex(ValueError, "all scheduler policy kinds"):
            replace(report, records=records[:-1])

    def test_replay_cannot_claim_match_for_different_outputs(self):
        with self.assertRaisesRegex(ValueError, "match flag"):
            replace(record(1, SchedulerPolicyKind.HOST_ADMISSION), replayed_output_digest_sha256="f" * 64)

    def test_offline_replay_cannot_consult_current_host(self):
        with self.assertRaisesRegex(ValueError, "current host"):
            replace(record(1, SchedulerPolicyKind.HOST_ADMISSION), current_host_state_consulted=True)


if __name__ == "__main__":
    unittest.main()
