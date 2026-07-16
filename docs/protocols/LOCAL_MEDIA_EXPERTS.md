# Local media experts

Phase 9.6 adds four separately routable local capabilities:

- `expert.vision.ocr-qwen3-vl-8b` — OCR through the installed Qwen3-VL model.
- `expert.vision.qwen3-vl-8b` — general image description through the same digest-bound model artifact.
- `expert.speech.faster-whisper-tiny-en` — local English speech recognition through Faster-Whisper on CPU/int8.
- `expert.speech.piper-lessac-medium` — local waveform synthesis through Piper.

The provider-neutral media ports accept explicit image/audio paths and return content digests. Media is never inferred from ambient desktop, camera, or microphone state. Application permissions must authorize observation or capture before these adapters receive a file.

## Live workstation evidence

`tools/run_media_expert_benchmark.py` generates a deterministic image, proves exact OCR and image description with `qwen3-vl:8b`, synthesizes a fixed phrase with Piper, and transcribes the resulting WAV with Faster-Whisper. The checked report records exact model/voice/tree digests and passed all four capabilities.

The optional runtime dependencies are isolated in the `media` project extra. Model files remain user-owned cache artifacts and package removal does not silently delete them.
