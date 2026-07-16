"""Live evidence contract for local media expert packages."""

from dataclasses import dataclass

MEDIA_EVIDENCE_CONTRACT_VERSION = "fam.expert.media-evidence/v1alpha1"


@dataclass(frozen=True, slots=True)
class MediaExpertEvidence:
    evidence_id: str
    vision_model_ref: str
    vision_artifact_sha256: str
    vision_description: str
    ocr_expected_text: str
    ocr_observed_text: str
    ocr_passed: bool
    tts_voice_ref: str
    tts_artifact_sha256: str
    tts_audio_sha256: str
    asr_model_ref: str
    asr_artifact_sha256: str
    asr_expected_text: str
    asr_observed_text: str
    asr_passed: bool
    passed: bool
    contract_version: str = MEDIA_EVIDENCE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        expected = self.ocr_passed and self.asr_passed and bool(self.vision_description.strip())
        if self.passed != expected:
            raise ValueError("media evidence pass must match all capability checks")
        for value in (
            self.vision_artifact_sha256, self.tts_artifact_sha256,
            self.tts_audio_sha256, self.asr_artifact_sha256,
        ):
            if len(value) != 64:
                raise ValueError("media evidence requires SHA-256 digests")
