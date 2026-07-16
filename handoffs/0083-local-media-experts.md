# Handoff 0083: Phase 9.6 local media experts

## Completed

- Added provider-neutral image analysis, ASR, and TTS contracts.
- Added Ollama multimodal, Faster-Whisper, and Piper adapters.
- Added four separate OCR, vision, speech-recognition, and TTS package identities/bindings.
- Added the isolated `media` optional dependency set.
- Downloaded and digest-bound the local Piper Lessac voice and Faster-Whisper Tiny English model.
- Ran live exact OCR, vision-description, TTS, and TTS-to-ASR checks; all passed.
- Added strict media evidence schema; rendered 99 schemas.

## Evidence

- `artifacts/expert_fabric/phase9.6/media-expert-workstation.json`
- `tests/integration/test_media_expert_evidence.py`
- `tests/unit/test_ollama_vision.py`
- `docs/protocols/LOCAL_MEDIA_EXPERTS.md`
- `docs/decisions/0082-media-experts-require-explicit-files.md`

## Next

Start Phase 9.7 with measured quality-per-byte, quality-per-second, and quality-per-joule selection reports. Energy values must come from an observed meter or be marked unavailable; do not manufacture joule estimates.
