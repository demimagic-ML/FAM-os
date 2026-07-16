#!/usr/bin/env python3
"""Run live OCR, vision, TTS, and ASR package evidence."""

import argparse
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from fam_os.adapters.media import FasterWhisperRecognizer, PiperSpeechSynthesizer
from fam_os.adapters.ollama import OllamaModelCatalog, OllamaSettings
from fam_os.adapters.ollama.vision import OllamaVisionAnalyzer
from fam_os.core.ports.media import ImageAnalysisRequest
from fam_os.experts.media_evidence import MediaExpertEvidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice-dir", type=Path, required=True)
    parser.add_argument("--whisper-dir", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    work = args.output.parent / "work"
    work.mkdir(parents=True, exist_ok=True)
    image_path, expected_ocr = _image(work)
    settings = OllamaSettings(args.ollama_url, 300)
    vision = OllamaVisionAnalyzer(settings, "qwen3-vl:8b")
    ocr = vision.analyze(ImageAnalysisRequest(image_path, "Read the large text exactly. Return only the text.", "ocr"))
    description = vision.analyze(ImageAnalysisRequest(image_path, "Briefly describe the image.", "vision"))
    phrase = "For all mankind, local intelligence is ready."
    voice_model = args.voice_dir / "en_US-lessac-medium.onnx"
    audio = PiperSpeechSynthesizer(voice_model, "en_US-lessac-medium").synthesize(phrase, work / "speech.wav")
    transcript = FasterWhisperRecognizer(download_root=args.whisper_dir).transcribe(audio.output_path)
    observed_ocr = ocr.text.strip()
    ocr_passed = _normalize(expected_ocr) in _normalize(observed_ocr)
    asr_passed = _normalize(phrase) == _normalize(transcript.text)
    evidence = MediaExpertEvidence(
        "phase9.6-workstation-v1", "qwen3-vl:8b",
        OllamaModelCatalog(settings).observe("qwen3-vl:8b").digest.value,
        description.text, expected_ocr, observed_ocr,
        ocr_passed,
        "en_US-lessac-medium", _digest(voice_model), audio.audio_sha256,
        transcript.model_ref, _tree_digest(args.whisper_dir), phrase, transcript.text,
        asr_passed, ocr_passed and asr_passed,
    )
    args.output.write_text(json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n")


def _image(work: Path):
    text = "FAM LOCAL 5080"
    image = Image.new("RGB", (900, 260), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 72)
    draw.rectangle((20, 20, 880, 240), outline="navy", width=8)
    draw.text((100, 85), text, fill="black", font=font)
    path = work / "ocr.png"
    image.save(path)
    return path, text


def _normalize(value):
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


if __name__ == "__main__":
    main()
