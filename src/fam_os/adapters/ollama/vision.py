"""Ollama multimodal image analysis adapter."""

import base64
import hashlib
import time
from dataclasses import dataclass

from fam_os.adapters.ollama.payloads import build_chat_payload
from fam_os.adapters.ollama.responses import parse_chat_response
from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.adapters.ollama.transport import JsonTransport, UrllibJsonTransport
from fam_os.core.ports.inference import InferenceMessage, InferenceRequest, MessageRole
from fam_os.core.ports.media import ImageAnalysisRequest, ImageAnalysisResult


@dataclass(slots=True)
class OllamaVisionAnalyzer:
    settings: OllamaSettings
    model_ref: str
    transport: JsonTransport | None = None

    def analyze(self, request: ImageAnalysisRequest) -> ImageAnalysisResult:
        image = request.image_path.read_bytes()
        inference = InferenceRequest(
            self.model_ref,
            (InferenceMessage(MessageRole.USER, request.prompt),),
            8192, 512, temperature=0,
        )
        payload = build_chat_payload(inference)
        messages = payload["messages"]
        if not isinstance(messages, list) or not isinstance(messages[0], dict):
            raise ValueError("Ollama chat payload did not contain a message")
        messages[0]["images"] = [base64.b64encode(image).decode("ascii")]
        transport = self.transport or UrllibJsonTransport()
        started = time.perf_counter()
        raw = transport.request(
            "POST", self.settings.endpoint("/api/chat"), payload,
            self.settings.timeout_seconds,
        )
        response = parse_chat_response(self.model_ref, raw, time.perf_counter() - started)
        return ImageAnalysisResult(
            response.content.strip(), self.model_ref, hashlib.sha256(image).hexdigest(),
        )
