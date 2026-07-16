import unittest

from fam_os.adapters.ollama.payloads import build_chat_payload, build_unload_payload
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, MessageRole


class OllamaPayloadTests(unittest.TestCase):
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

    def test_builds_prototype_compatible_unload_payload(self) -> None:
        self.assertEqual(build_unload_payload("model"), {"model": "model", "keep_alive": 0})

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
