import json
import unittest
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.core.ports.embedding import EmbeddingRequest
from fam_os.adapters.ollama.errors import OllamaTransportError
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, InferenceTool, MessageRole,
)


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
    def test_lists_available_model_names(self) -> None:
        transport = FakeTransport([{"models": [
            {"name": "qwen2.5-coder:7b"},
            {"model": "qwen3-coder:30b"},
        ]}])
        runtime = OllamaRuntime(OllamaSettings("http://localhost:11434", 15), transport)

        self.assertEqual(
            ("qwen2.5-coder:7b", "qwen3-coder:30b"),
            runtime.available_models(),
        )
    def test_normalizes_tagged_template_tool_call(self) -> None:
        transport = FakeTransport([{
            "message": {"role": "assistant", "content": (
                '<tool_call>{"name":"read_file","arguments":'
                '{"path":"README.md"}}</tool_call>'
            )},
        }])
        runtime = OllamaRuntime(OllamaSettings("http://localhost:11434", 15), transport)

        result = runtime.chat(InferenceRequest(
            "qwen", (InferenceMessage(MessageRole.USER, "Read it"),), 4096, 128,
            tools=(InferenceTool(
                "read_file", "Read a file.", {
                    "type": "object", "properties": {
                        "path": {"type": "string"},
                    }, "required": ["path"],
                },
            ),), tool_choice="auto",
        ))

        self.assertEqual("read_file", result.tool_calls[0].name)
    def test_normalizes_template_tool_json_only_for_offered_schema(self) -> None:
        transport = FakeTransport([{
            "message": {
                "role": "assistant",
                "content": '{"name":"read_file","arguments":{"path":"README.md"}}',
            },
        }])
        runtime = OllamaRuntime(OllamaSettings("http://localhost:11434", 15), transport)

        result = runtime.chat(InferenceRequest(
            "qwen", (InferenceMessage(MessageRole.USER, "Read it"),), 4096, 128,
            tools=(InferenceTool(
                "read_file", "Read a file.", {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            ),), tool_choice="auto",
        ))

        self.assertEqual("", result.content)
        self.assertEqual("read_file", result.tool_calls[0].name)
        self.assertEqual({"path": "README.md"}, result.tool_calls[0].arguments)

    def test_embed_uses_batch_endpoint_and_parses_vectors(self) -> None:
        transport = FakeTransport([{
            "embeddings": [[1, 0.5], [0.25, 1]], "prompt_eval_count": 7,
        }])
        times = iter((2.0, 2.4))
        runtime = OllamaRuntime(
            OllamaSettings("http://localhost:11434", 15), transport,
            clock=lambda: next(times),
        )

        result = runtime.embed(EmbeddingRequest("embed-model", ("a", "b")))

        self.assertEqual(((1.0, 0.5), (0.25, 1.0)), result.vectors)
        self.assertEqual(7, result.prompt_tokens)
        self.assertEqual("http://localhost:11434/api/embed", transport.requests[0][1])
        self.assertEqual(["a", "b"], transport.requests[0][2]["input"])

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

    def test_prewarms_without_prompt_content_and_proves_residency(self) -> None:
        loaded = json.loads((FIXTURES / "ps-response.json").read_text())
        transport = FakeTransport([{}, loaded])
        runtime = OllamaRuntime(OllamaSettings("http://localhost:11434", 15), transport)

        runtime.prewarm("fam-test-model:latest", "10m")

        self.assertEqual(
            {
                "model": "fam-test-model:latest",
                "stream": False,
                "keep_alive": "10m",
            },
            transport.requests[0][2],
        )
        self.assertNotIn("prompt", transport.requests[0][2])
        self.assertEqual("GET", transport.requests[1][0])

    def test_prewarms_embedding_model_through_embedding_endpoint(self) -> None:
        loaded = {
            "models": [{
                "name": "embed-model:latest", "size": 1024,
                "size_vram": 1024, "details": {},
            }],
        }
        transport = FakeTransport([{
            "embeddings": [[0.25, 0.75]], "prompt_eval_count": 5,
        }, loaded])
        times = iter((1.0, 1.1, 1.2))
        runtime = OllamaRuntime(
            OllamaSettings("http://localhost:11434", 15), transport,
            clock=lambda: next(times),
        )

        runtime.prewarm_embedding("embed-model:latest", "10m")

        method, url, payload, _ = transport.requests[0]
        self.assertEqual("POST", method)
        self.assertEqual("http://localhost:11434/api/embed", url)
        self.assertEqual("embed-model:latest", payload["model"])
        self.assertEqual("10m", payload["keep_alive"])
        self.assertEqual(
            ["FAM_OS embedding residency probe"], payload["input"],
        )
        self.assertEqual("GET", transport.requests[1][0])

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
