import base64
import unittest

from fam_os.adapters.ollama.payloads import (
    build_chat_payload,
    build_prewarm_payload,
    build_unload_payload,
)
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, InferenceTool, InferenceToolCall,
    MessageRole,
)


class OllamaPayloadTests(unittest.TestCase):
    def test_translates_native_tools_and_tool_result_messages(self) -> None:
        request = InferenceRequest(
            "qwen2.5-coder:7b",
            (
                InferenceMessage(MessageRole.USER, "Read README.md"),
                InferenceMessage(
                    MessageRole.ASSISTANT, "",
                    tool_calls=(InferenceToolCall(
                        "call-1", "read_file", {"path": "README.md"},
                    ),),
                ),
                InferenceMessage(
                    MessageRole.TOOL, "file content",
                    tool_call_id="call-1", tool_name="read_file",
                ),
            ),
            4096, 256, json_output=True,
            tools=(InferenceTool(
                "read_file", "Read a workspace file.", {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            ),),
            tool_choice="auto",
        )

        payload = build_chat_payload(request)

        self.assertNotIn("format", payload)
        self.assertEqual("read_file", payload["tools"][0]["function"]["name"])
        self.assertEqual(
            {"path": "README.md"},
            payload["messages"][1]["tool_calls"][0]["function"]["arguments"],
        )
        self.assertEqual("tool", payload["messages"][2]["role"])
        self.assertEqual("read_file", payload["messages"][2]["tool_name"])

    def test_translates_provider_neutral_chat_request(self) -> None:
        request = InferenceRequest(
            "fam-test-model",
            (
                InferenceMessage(MessageRole.SYSTEM, "Route the task"),
                InferenceMessage(MessageRole.USER, "Write a test"),
            ),
            context_tokens=2048,
            max_output_tokens=100,
            keep_alive="5m",
            json_output=True,
            temperature=0.25,
            seed=7,
        )
        payload = build_chat_payload(request)

        self.assertEqual(payload["model"], "fam-test-model")
        self.assertEqual(payload["format"], "json")
        self.assertEqual(payload["messages"][1]["role"], "user")
        self.assertEqual(payload["options"]["num_ctx"], 2048)
        self.assertEqual(payload["options"]["temperature"], 0.25)
        self.assertFalse(payload["think"])

    def test_omits_seed_when_runtime_may_choose(self) -> None:
        request = InferenceRequest(
            "model",
            (InferenceMessage(MessageRole.USER, "hello"),),
            1024,
            16,
            seed=None,
        )
        self.assertNotIn("seed", build_chat_payload(request)["options"])

    def test_encodes_provider_neutral_message_images(self) -> None:
        content = b"image-bytes"
        request = InferenceRequest(
            "vision:model",
            (InferenceMessage(MessageRole.USER, "read text", (content,)),),
            4096,
            128,
        )
        message = build_chat_payload(request)["messages"][0]
        self.assertEqual(
            [base64.b64encode(content).decode("ascii")], message["images"],
        )

    def test_builds_prototype_compatible_unload_payload(self) -> None:
        self.assertEqual(build_unload_payload("model"), {"model": "model", "keep_alive": 0})

    def test_builds_content_free_model_prewarm_payload(self) -> None:
        self.assertEqual(
            build_prewarm_payload("model", "10m"),
            {"model": "model", "stream": False, "keep_alive": "10m"},
        )

    def test_translates_explicit_accelerator_layer_placement(self) -> None:
        request = InferenceRequest(
            "qwen:7b",
            (InferenceMessage(MessageRole.USER, "hello"),),
            4096,
            128,
            accelerator_layer_count=24,
            main_accelerator_index=0,
        )
        payload = build_chat_payload(request)
        self.assertEqual(payload["options"]["num_gpu"], 24)
        self.assertEqual(payload["options"]["main_gpu"], 0)

    def test_omits_provider_placement_when_scheduler_did_not_choose_it(self) -> None:
        request = InferenceRequest(
            "qwen:7b", (InferenceMessage(MessageRole.USER, "hello"),), 4096, 128
        )
        options = build_chat_payload(request)["options"]
        self.assertNotIn("num_gpu", options)
        self.assertNotIn("main_gpu", options)


if __name__ == "__main__":
    unittest.main()
