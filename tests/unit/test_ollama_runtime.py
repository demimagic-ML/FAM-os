import json
import unittest
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.adapters.ollama.errors import OllamaTransportError
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, MessageRole


FIXTURES = Path(__file__).parents[1] / "fixtures" / "ollama"


class FakeTransport:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str, object, float]] = []

    def request(
        self, method: str, url: str, payload: dict[str, object] | None, timeout_seconds: float
    ) -> dict[str, object]:
        self.requests.append((method, url, payload, timeout_seconds))
        return self.responses.pop(0)


class OllamaRuntimeTests(unittest.TestCase):
    def test_chat_uses_transport_and_measures_wall_time(self) -> None:
        response = json.loads((FIXTURES / "chat-response.json").read_text())
        transport = FakeTransport([response])
        times = iter((10.0, 12.0))
        runtime = OllamaRuntime(
            OllamaSettings("http://127.0.0.1:11434/", 30),
            transport,
            lambda: next(times),
        )
        request = InferenceRequest(
            "fam-test-model",
            (InferenceMessage(MessageRole.USER, "hello"),),
            2048,
            32,
        )

        result = runtime.chat(request)

        self.assertEqual(result.metrics.wall_seconds, 2.0)
        self.assertEqual(transport.requests[0][0:2], ("POST", "http://127.0.0.1:11434/api/chat"))

    def test_lists_and_unloads_models_through_expected_endpoints(self) -> None:
        loaded = json.loads((FIXTURES / "ps-response.json").read_text())
        transport = FakeTransport([loaded, {}, {"models": []}])
        runtime = OllamaRuntime(OllamaSettings("http://localhost:11434", 15), transport)

        self.assertEqual(runtime.loaded_models()[0].context_tokens, 2048)
        runtime.unload("fam-test-model:latest")

        self.assertEqual(transport.requests[0][0:3], ("GET", "http://localhost:11434/api/ps", None))
        self.assertEqual(transport.requests[1][1], "http://localhost:11434/api/generate")
        self.assertEqual(transport.requests[1][2], {"model": "fam-test-model:latest", "keep_alive": 0})
        self.assertEqual(transport.requests[2][0:3], ("GET", "http://localhost:11434/api/ps", None))

    def test_waits_until_unloaded_model_disappears(self) -> None:
        loaded = json.loads((FIXTURES / "ps-response.json").read_text())
        transport = FakeTransport([{}, loaded, {"models": []}])
        sleeps: list[float] = []
        times = iter((0.0, 0.1))
        runtime = OllamaRuntime(
            OllamaSettings("http://localhost:11434", 15),
            transport,
            clock=lambda: next(times),
            sleeper=sleeps.append,
        )

        runtime.unload("fam-test-model:latest")

        self.assertEqual(sleeps, [0.05])
        self.assertEqual(len(transport.requests), 3)

    def test_reports_unconfirmed_unload(self) -> None:
        loaded = json.loads((FIXTURES / "ps-response.json").read_text())
        transport = FakeTransport([{}, loaded])
        times = iter((0.0, 0.1))
        runtime = OllamaRuntime(
            OllamaSettings(
                "http://localhost:11434",
                15,
                unload_timeout_seconds=0.05,
            ),
            transport,
            clock=lambda: next(times),
            sleeper=lambda _: None,
        )

        with self.assertRaisesRegex(OllamaTransportError, "remained loaded"):
            runtime.unload("fam-test-model:latest")


if __name__ == "__main__":
    unittest.main()
