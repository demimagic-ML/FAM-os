"""Bounded local Ollama summarization for the acceptance workflow."""

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.core.ports.inference import (
    InferenceMessage, InferenceRequest, MessageRole,
)


class LocalReadmeSummarizer:
    def __init__(self, model_ref="qwen3:1.7b"):
        self.model_ref = model_ref
        self.runtime = OllamaRuntime(OllamaSettings("http://127.0.0.1:11434", 120))

    def summarize(self, content: str, mcp_context: str | None = None):
        context = f"\nMCP context: {mcp_context}" if mcp_context else ""
        request = InferenceRequest(
            self.model_ref,
            (
                InferenceMessage(
                    MessageRole.SYSTEM,
                    "Summarize only the supplied README in three concise sentences. "
                    "Do not invent capabilities.",
                ),
                InferenceMessage(MessageRole.USER, content + context),
            ),
            context_tokens=8192, max_output_tokens=220, keep_alive="5m",
        )
        response = self.runtime.chat(request)
        if not response.content.strip():
            raise RuntimeError("local summary expert returned empty content")
        return response
