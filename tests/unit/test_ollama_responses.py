import json
import unittest
from pathlib import Path

from fam_os.adapters.ollama.errors import OllamaProtocolError
from fam_os.adapters.ollama.responses import parse_chat_response, parse_loaded_models


FIXTURES = Path(__file__).parents[1] / "fixtures" / "ollama"


class OllamaResponseTests(unittest.TestCase):
    def test_converts_nanosecond_metrics(self) -> None:
        payload = json.loads((FIXTURES / "chat-response.json").read_text())
        response = parse_chat_response("fam-test-model", payload, wall_seconds=2.0)

        self.assertEqual(response.content, '{"route":"code"}')
        self.assertEqual(response.metrics.load_seconds, 1.5)
        self.assertEqual(response.metrics.prompt_tokens, 20)
        self.assertEqual(response.metrics.output_tokens, 10)
        self.assertEqual(response.metrics.generation_tokens_per_second, 20.0)

    def test_rejects_missing_message_content(self) -> None:
        with self.assertRaisesRegex(OllamaProtocolError, "message.content"):
            parse_chat_response("model", {"message": {}}, 0.1)

    def test_parses_loaded_model_resources(self) -> None:
        payload = json.loads((FIXTURES / "ps-response.json").read_text())
        loaded = parse_loaded_models(payload)[0]

        self.assertEqual(loaded.model_ref, "fam-test-model:latest")
        self.assertEqual(loaded.resident_bytes, 2_000_000_000)
        self.assertEqual(loaded.accelerator_bytes, 1_000_000_000)
        self.assertEqual(loaded.context_tokens, 2048)

    def test_rejects_invalid_models_shape(self) -> None:
        with self.assertRaisesRegex(OllamaProtocolError, "requires a list"):
            parse_loaded_models({"models": {}})


if __name__ == "__main__":
    unittest.main()

