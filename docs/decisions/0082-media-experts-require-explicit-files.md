# ADR 0082: Media experts require explicit file inputs

- Status: accepted
- Date: 2026-07-16

## Decision

OCR, vision, speech recognition, and TTS are separate expert packages behind provider-neutral media contracts. Image and audio analysis require an explicitly authorized file. TTS requires explicit text and output path. The expert layer does not independently activate cameras, microphones, screen capture, or speakers.

Qwen3-VL initially backs OCR and vision, Faster-Whisper Tiny English backs ASR, and Piper Lessac Medium backs TTS. Each binding records the exact locally observed artifact digest.

## Consequences

- Shared model weights do not collapse OCR and general vision permissions.
- Application Fabric remains responsible for acquisition and user approval.
- Media experts can be upgraded independently while preserving the port.
- English-only ASR is declared honestly; multilingual support requires another package and benchmark.
