"""Quantized variant and calibration metadata."""

from dataclasses import dataclass

FACTORY_QUANTIZATION_CONTRACT_VERSION = "fam.factory.quantization/v1alpha1"


@dataclass(frozen=True, slots=True)
class QuantizedVariant:
    variant_id: str
    source_expert_id: str
    format: str
    bits_per_weight: int
    artifact_sha256: str
    artifact_bytes: int
    calibration_dataset_sha256: str
    calibration_quality: float
    maximum_quality_drop: float
    passed: bool
    contract_version: str = FACTORY_QUANTIZATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        expected = self.bits_per_weight in (2, 3, 4, 5, 6, 8)
        expected = expected and self.calibration_quality >= 1 - self.maximum_quality_drop
        if self.passed != expected or self.artifact_bytes <= 0:
            raise ValueError("quantized variant does not satisfy calibration")
