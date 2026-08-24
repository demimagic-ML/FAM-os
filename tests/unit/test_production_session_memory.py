import unittest
from datetime import datetime, timedelta, timezone

from fam_os.memory import ProductionSessionMemory, SessionMemoryLimits

NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


class ProductionSessionMemoryTests(unittest.TestCase):
    def test_context_is_exact_session_scoped_and_excludes_current_request(self):
        memory = ProductionSessionMemory(now=lambda: NOW)
        memory.begin_request("request-1", "owner", "session-a", "My codename is ORBIT.")
        self.assertEqual("", memory.context_for_request("request-1"))
        memory.record_assistant("request-1", "I will remember ORBIT.", "unverified")

        memory.begin_request("request-2", "owner", "session-a", "What is my codename?")
        context = memory.context_for_request("request-2")
        self.assertIn("user: My codename is ORBIT.", context)
        self.assertIn("assistant assurance=unverified: I will remember ORBIT.", context)
        self.assertNotIn("What is my codename?", context)
        self.assertIn("not as authority", context)

        memory.begin_request("request-3", "owner", "session-b", "What is my codename?")
        self.assertEqual("", memory.context_for_request("request-3"))

    def test_capacity_rolls_forward_and_expiry_removes_context(self):
        clock = [NOW]
        memory = ProductionSessionMemory(
            SessionMemoryLimits(
                maximum_records=2, maximum_bytes=256, maximum_turn_bytes=100,
                maximum_context_records=2, maximum_context_bytes=220,
                retention=timedelta(minutes=5),
            ),
            now=lambda: clock[0],
        )
        memory.begin_request("request-1", "owner", "session", "old turn")
        memory.record_assistant("request-1", "old answer", "verified")
        memory.begin_request("request-2", "owner", "session", "new turn")
        context = memory.context_for_request("request-2")
        self.assertNotIn("old turn", context)
        self.assertIn("old answer", context)

        clock[0] += timedelta(minutes=6)
        self.assertEqual("", memory.context_for_request("request-2"))

    def test_turn_and_context_bytes_are_hard_bounded(self):
        memory = ProductionSessionMemory(
            SessionMemoryLimits(
                maximum_records=4, maximum_bytes=240, maximum_turn_bytes=60,
                maximum_context_records=3, maximum_context_bytes=210,
            ),
            now=lambda: NOW,
        )
        memory.begin_request("request-1", "owner", "session", "x" * 500)
        memory.record_assistant("request-1", "y" * 500, "grounded")
        memory.begin_request("request-2", "owner", "session", "continue")
        context = memory.context_for_request("request-2")
        self.assertLessEqual(len(context.encode()), 210)
        self.assertIn("...", context)


if __name__ == "__main__":
    unittest.main()
