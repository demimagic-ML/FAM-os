import unittest

from fam_os.core.agent import (
    AgentGoalLedger,
    AgentToolDescriptor,
    AgentToolEffect,
    AgentToolResult,
)
from fam_os.core.agent.orchestration import (
    AgentContextCompiler,
    EvidenceVerifier,
    RecoveryRouter,
)
from fam_os.core.ports.inference import InferenceMessage, MessageRole


class AgentOrchestrationTests(unittest.TestCase):
    def test_context_reset_keeps_typed_goal_changes_and_latest_error(self):
        compiler = AgentContextCompiler()
        descriptor = AgentToolDescriptor(
            "read_file", "Read.", AgentToolEffect.OBSERVE,
            {"type": "object", "properties": {}, "required": []},
        )
        results = (
            AgentToolResult(
                "write", "write_file", True, "written", {
                    "verified": True, "operation": "write_file", "path": "app.py",
                },
            ),
            AgentToolResult("missing", "run_command", False, "missing executable"),
        )
        compiled = compiler.compile(
            system="system", ledger=AgentGoalLedger("Build it", "Plan", "Continue"),
            profile="workspace", prior_context="workspace",
            conversation_history="history",
            event_messages=tuple(
                InferenceMessage(MessageRole.USER, "x" * 4_000) for _ in range(8)
            ),
            tool_results=results, descriptors=(descriptor,), context_tokens=4_096,
            maximum_output_tokens=1_024, generation=2, compaction_count=2,
        )

        self.assertTrue(compiled.compacted)
        self.assertTrue(compiled.reset)
        self.assertEqual(3, len(compiled.messages))
        state = compiled.messages[1].content
        self.assertIn("app.py", state)
        self.assertIn("missing executable", state)
        self.assertIn("Build it", state)

    def test_external_evidence_verifier_ignores_model_claims(self):
        verifier = EvidenceVerifier()
        self.assertFalse(verifier.evaluate(()).accepted)
        accepted = verifier.evaluate((AgentToolResult(
            "call", "create_directory", True, "created",
            {"verified": True, "kind": "directory"},
        ),))
        self.assertTrue(accepted.accepted)

    def test_recovery_router_classifies_missing_executable(self):
        directive = RecoveryRouter().classify(AgentToolResult(
            "call", "run_command", False, "RuntimeError: execvp: no such file",
        ))
        self.assertEqual("missing_executable", directive.category)
        self.assertEqual(1, directive.retry_limit)


if __name__ == "__main__":
    unittest.main()
