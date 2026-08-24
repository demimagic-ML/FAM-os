import json
import subprocess
import unittest
from pathlib import Path


class ConsoleTaskUpdateTests(unittest.TestCase):
    def test_terminal_snapshot_cannot_be_replaced_by_queued_live_update(self) -> None:
        script = Path(__file__).parents[2] / (
            "src/fam_os/console/static/task_updates.js"
        )
        program = """
const updates = require(process.argv[1]);
const active = {session_id: "task-1", revision: 2, state: "running"};
const terminal = {session_id: "task-1", revision: 2, state: "terminal"};
const stale = {session_id: "task-1", revision: 1, state: "running"};
const other = {session_id: "task-2", revision: 9, state: "terminal"};
const modelAnswer = updates.resultPresentation({
  result_kind: "conversation_answer", verified: false, evidence_ids: ["candidate"],
});
const receipt = updates.resultPresentation({
  result_kind: "action_receipt", verified: true, evidence_ids: ["postcondition"],
});
const changeProposal = updates.resultPresentation({
  result_kind: "changeset_proposal", verified: false, evidence_ids: [],
});
const changeReceipt = updates.resultPresentation({
  result_kind: "verified_changeset_receipt", verified: true,
  evidence_ids: ["postcondition"],
});
const publicationProposal = updates.resultPresentation({
  result_kind: "publication_proposal", verified: false, evidence_ids: [],
});
const publicationReceipt = updates.resultPresentation({
  result_kind: "publication_receipt", verified: true,
  evidence_ids: ["remote-postcondition"],
});
const unverifiedExecution = updates.resultPresentation({
  result_kind: "engineering_execution", assurance: "executed_unverified",
  verified: false, evidence_ids: ["effect"],
});
const waivedExecution = updates.resultPresentation({
  result_kind: "engineering_execution", assurance: "verification_waived",
  verified: false, evidence_ids: ["effect", "waiver"],
});
console.log(JSON.stringify({
  terminalAfterActive: updates.accepts(active, terminal),
  activeAfterTerminal: updates.accepts(terminal, active),
  staleAfterActive: updates.accepts(active, stale),
  otherTask: updates.accepts(active, other),
  modelAnswer,
  receipt,
  changeProposal,
  changeReceipt,
  publicationProposal,
  publicationReceipt,
  unverifiedExecution,
  waivedExecution,
  notTaken: updates.displayStepState("terminal", "pending"),
}));
"""
        completed = subprocess.run(
            ("node", "-e", program, str(script)),
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual({
            "terminalAfterActive": True,
            "activeAfterTerminal": False,
            "staleAfterActive": False,
            "otherTask": False,
            "modelAnswer": {
                "label": "MODEL ANSWER · NO MACHINE ACTION",
                "canReverse": False,
                "evidenceLabel": "No action receipt",
            },
            "receipt": {
                "label": "VERIFIED ACTION RECEIPT",
                "canReverse": True,
                "evidenceLabel": "1 verified action evidence record",
            },
            "changeProposal": {
                "label": "ENGINEERING CHANGESET PROPOSED · NOT EXECUTED",
                "canReverse": False,
                "evidenceLabel": "No action receipt",
            },
            "changeReceipt": {
                "label": "VERIFIED ENGINEERING CHANGESET RECEIPT",
                "canReverse": True,
                "evidenceLabel": "1 verified engineering evidence record",
            },
            "publicationProposal": {
                "label": "PUBLICATION PROPOSED · NOT PUBLISHED",
                "canReverse": False,
                "evidenceLabel": "No action receipt",
            },
            "publicationReceipt": {
                "label": "VERIFIED PUBLICATION RECEIPT",
                "canReverse": False,
                "evidenceLabel": "1 verified publication evidence record",
            },
            "unverifiedExecution": {
                "label": "ENGINEERING EXECUTED · UNVERIFIED",
                "canReverse": False,
                "evidenceLabel": "1 engineering effect evidence record",
            },
            "waivedExecution": {
                "label": "ENGINEERING EXECUTED · VERIFICATION WAIVED",
                "canReverse": False,
                "evidenceLabel": "2 engineering effect evidence records",
            },
            "notTaken": "not_taken",
        }, result)


if __name__ == "__main__":
    unittest.main()
