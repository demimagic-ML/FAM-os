import os
import unittest

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, MessageRole


class OllamaRuntimeSmokeTests(unittest.TestCase):
    def test_local_chat_metrics_and_lifecycle(self) -> None:
        model = os.environ.get("FAM_OLLAMA_SMOKE_MODEL")
        if not model:
            self.skipTest("set FAM_OLLAMA_SMOKE_MODEL for an opt-in live inference test")
        base_url = os.environ.get("FAM_OLLAMA_URL", "http://127.0.0.1:11434")
        runtime = OllamaRuntime(OllamaSettings(base_url, 300))
        before = {loaded.model_ref for loaded in runtime.loaded_models()}
        request = InferenceRequest(
            model,
            (InferenceMessage(MessageRole.USER, "Reply with only the word OK."),),
            context_tokens=512,
            max_output_tokens=8,
            keep_alive="0s" if model not in before else "5m",
        )

        response = runtime.chat(request)

        self.assertTrue(response.content.strip())
        self.assertGreaterEqual(response.metrics.load_seconds, 0)
        self.assertGreater(response.metrics.output_tokens, 0)
        if model not in before:
            runtime.unload(model)


if __name__ == "__main__":
    unittest.main()

