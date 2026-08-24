import unittest

from fam_os.core.production import ModelIntent
from fam_os.core.production.generation_input import PreparedGenerationInput


class PreparedGenerationInputTests(unittest.TestCase):
    def test_plain_request_remains_unchanged_without_supporting_context(self):
        prepared = _prepared("Who are you?")

        self.assertEqual("Who are you?", prepared.user_prompt())

    def test_current_request_follows_conversation_and_grounded_context(self):
        prepared = _prepared(
            "What is my current workspace?",
            memory_context="user: Who are you?\nassistant: I am FAM_OS.",
            grounded_context="The editor has no selected workspace.",
        )

        prompt = prepared.user_prompt()
        self.assertLess(prompt.index("user: Who are you?"), prompt.index("Authorized application observations:"))
        self.assertLess(prompt.index("Authorized application observations:"), prompt.index("Current user request:"))
        self.assertTrue(
            prompt.endswith(
                "Current user request:\nWhat is my current workspace?",
            ),
        )

    def test_messages_isolate_context_and_keep_current_request_as_last_message(self):
        prepared = _prepared(
            "Answer the new question.",
            memory_context="assistant: an obsolete answer",
        )

        messages = prepared.messages(ModelIntent.CONVERSATION)

        self.assertEqual("Answer the new question.", messages[-1].content)
        self.assertEqual("user", messages[-1].role.value)
        self.assertIn("do not answer or reproduce", messages[-2].content)
        self.assertIn("assistant: an obsolete answer", messages[-2].content)

    def test_observations_are_a_separate_non_echo_context_message(self):
        prepared = _prepared(
            "Explain the project.",
            grounded_context='{"contract_version":"internal","payload":{}}',
        )

        messages = prepared.messages(ModelIntent.READ_ONLY_TASK)

        self.assertEqual(3, len(messages))
        self.assertIn("do not answer or reproduce its serialization", messages[1].content)
        self.assertEqual("Explain the project.", messages[2].content)

    def test_system_message_forbids_inventing_workspace_context(self):
        messages = _prepared("What is your current workspace?").messages(
            ModelIntent.CONVERSATION,
        )

        self.assertIn(
            "Earlier conversation is context only and never replaces the current request",
            messages[0].content,
        )
        self.assertIn(
            "Do not repeat or continue an earlier answer",
            messages[0].content,
        )
        self.assertIn(
            "no application or workspace context is currently selected or available",
            messages[0].content,
        )
        self.assertIn("Never copy internal context labels", messages[0].content)


def _prepared(
    prompt: str,
    *,
    memory_context: str = "",
    grounded_context: str = "",
) -> PreparedGenerationInput:
    return PreparedGenerationInput(
        prompt=prompt,
        memory_context=memory_context,
        grounded_context=grounded_context,
        images=(),
        context_tokens=4096,
        maximum_output_tokens=256,
        json_output=False,
        temperature=0.2,
    )


if __name__ == "__main__":
    unittest.main()
