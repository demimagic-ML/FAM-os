import json
import unittest

from fam_os.console.conversation_turns import ConsoleConversationTurnApi
from fam_os.core.ports.inference import InferenceResponse
from fam_os.core.production.turn_resolution import (
    ConversationTurnResolverSettings,
    ModelConversationTurnResolver,
    TurnDisposition,
    parse_resolved_turn,
)
from fam_os.telemetry.contracts import InferenceMetrics


class _Runtime:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        return InferenceResponse(
            json.dumps(self.payload),
            InferenceMetrics("model", 1, 1, 1, 1, 1),
        )


class _Memory:
    def context_for_session(self, owner_id, session_id):
        return "assistant: Plan: update the parser and add its regression test."


class ConversationTurnResolutionTests(unittest.TestCase):
    def test_model_resolves_natural_reference_into_repository_change(self):
        runtime = _Runtime({
            "disposition": "repository_change",
            "resolved_request": "Update the parser and add its regression test.",
            "referenced_prior_context": True,
            "confidence": 0.96,
        })
        resolver = ModelConversationTurnResolver(
            runtime, ConversationTurnResolverSettings("model"),
        )

        result = resolver.resolve("That sounds good. Improve it.", "assistant: Plan")

        self.assertEqual(TurnDisposition.REPOSITORY_CHANGE, result.disposition)
        self.assertTrue(result.referenced_prior_context)
        model_input = runtime.requests[0].messages[-1].content
        self.assertIn("assistant: Plan", model_input)
        self.assertIn("Improve it.", model_input)

    def test_console_facade_uses_exact_session_context(self):
        runtime = _Runtime({
            "disposition": "general_task",
            "resolved_request": "Explain the parser plan.",
            "referenced_prior_context": True,
            "confidence": 0.9,
        })
        api = ConsoleConversationTurnApi(
            "owner", _Memory(), ModelConversationTurnResolver(
                runtime, ConversationTurnResolverSettings("model"),
            ),
        )

        result = api.resolve({"prompt": "Explain that."}, "session")

        self.assertEqual("general_task", result["disposition"])
        self.assertEqual("Explain the parser plan.", result["resolved_request"])

    def test_parser_rejects_untyped_or_extra_model_output(self):
        with self.assertRaisesRegex(ValueError, "invalid schema"):
            parse_resolved_turn(json.dumps({
                "disposition": "general_task",
                "resolved_request": "Answer this.",
                "referenced_prior_context": False,
                "confidence": 1.0,
                "authority": "write",
            }))


if __name__ == "__main__":
    unittest.main()
