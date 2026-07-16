"""Local Faster-Whisper speech recognition and Piper synthesis adapters."""

import hashlib
import wave
from dataclasses import dataclass
from pathlib import Path

from fam_os.core.ports.media import SpeechRecognitionResult, SpeechSynthesisResult


@dataclass(slots=True)
class FasterWhisperRecognizer:
    model_ref: str = "tiny.en"
    device: str = "cpu"
    compute_type: str = "int8"
    download_root: Path | None = None

    def transcribe(self, audio_path: Path) -> SpeechRecognitionResult:
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]

        model = WhisperModel(
            self.model_ref, device=self.device, compute_type=self.compute_type,
            download_root=str(self.download_root) if self.download_root else None,
        )
        segments, info = model.transcribe(str(audio_path), beam_size=1)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return SpeechRecognitionResult(
            text, info.language, self.model_ref, _digest(audio_path),
        )


@dataclass(slots=True)
class PiperSpeechSynthesizer:
    model_path: Path
    voice_ref: str

    def synthesize(self, text: str, output_path: Path) -> SpeechSynthesisResult:
        from piper import PiperVoice

        output_path.parent.mkdir(parents=True, exist_ok=True)
        voice = PiperVoice.load(self.model_path)
        with wave.open(str(output_path), "wb") as output:
            voice.synthesize_wav(text, output)
        return SpeechSynthesisResult(output_path, self.voice_ref, _digest(output_path))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
