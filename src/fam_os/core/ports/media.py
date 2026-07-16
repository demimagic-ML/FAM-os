"""Provider-neutral local media expert contracts."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

MEDIA_CONTRACT_VERSION = "fam.media/v1alpha1"


@dataclass(frozen=True, slots=True)
class ImageAnalysisRequest:
    image_path: Path
    prompt: str
    mode: str


@dataclass(frozen=True, slots=True)
class ImageAnalysisResult:
    text: str
    model_ref: str
    image_sha256: str


@dataclass(frozen=True, slots=True)
class SpeechRecognitionResult:
    text: str
    language: str
    model_ref: str
    audio_sha256: str


@dataclass(frozen=True, slots=True)
class SpeechSynthesisResult:
    output_path: Path
    voice_ref: str
    audio_sha256: str


class ImageAnalyzer(Protocol):
    def analyze(self, request: ImageAnalysisRequest) -> ImageAnalysisResult: ...


class SpeechRecognizer(Protocol):
    def transcribe(self, audio_path: Path) -> SpeechRecognitionResult: ...


class SpeechSynthesizer(Protocol):
    def synthesize(self, text: str, output_path: Path) -> SpeechSynthesisResult: ...
