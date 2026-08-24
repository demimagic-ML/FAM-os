import unittest
from datetime import datetime, timezone

from fam_os.core.engineering import NaturalEngineeringConversation
from fam_os.core.engineering.repository import ArchitectureArea
from fam_os.core.engineering.repository.planning import (
    ArchitectureDecision,
    ArchitectureProposal,
)


NOW = datetime(2026, 7, 19, 21, 0, tzinfo=timezone.utc)


class NaturalEngineeringConversationTests(unittest.TestCase):
    def test_follow_up_requires_a_plan_in_the_same_session_and_workspace(self):
        conversation = NaturalEngineeringConversation()

        with self.assertRaisesRegex(ValueError, "no approved plan"):
            conversation.resolve(
                "owner-1", "session-1", "/workspace/a", "Implement the plan.",
            )

        conversation.remember(
            "owner-1", "session-1", "/workspace/a", _proposal(),
        )
        resolved = conversation.resolve(
            "owner-1", "session-1", "/workspace/a", "Implement the plan.",
        )

        self.assertIn("the only source of authority", resolved)
        self.assertIn("Decision-complete design", resolved)
        with self.assertRaisesRegex(ValueError, "no approved plan"):
            conversation.resolve(
                "owner-1", "session-2", "/workspace/a", "Implement the plan.",
            )
        with self.assertRaisesRegex(ValueError, "no approved plan"):
            conversation.resolve(
                "owner-1", "session-1", "/workspace/b", "Implement the plan.",
            )

    def test_self_contained_request_does_not_require_conversation_state(self):
        prompt = "Create src/status.js and add a Node test for it."
        self.assertEqual(
            prompt,
            NaturalEngineeringConversation().resolve(
                "owner-1", None, "/workspace/a", prompt,
            ),
        )


def _proposal() -> ArchitectureProposal:
    decisions = tuple(
        ArchitectureDecision(
            area, True, f"Implement the {area.value} improvement.",
            ("package.json", "src/app.ts"),
        )
        for area in ArchitectureArea
    )
    return ArchitectureProposal(
        "architecture-1", "task-plan", "analysis-1", NOW,
        "Decision-complete design for improve the project", decisions,
        ("tests/app.test.ts",), True,
    )


if __name__ == "__main__":
    unittest.main()
