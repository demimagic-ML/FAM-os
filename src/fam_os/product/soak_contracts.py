"""Contracts for extended production resource and recovery qualification."""

from dataclasses import asdict, dataclass


SOAK_CONTRACT_VERSION = "fam.product.soak/v1alpha1"


@dataclass(frozen=True, slots=True)
class SoakReport:
    profile_id: str
    duration_seconds: float
    samples: int
    rss_start_bytes: int
    rss_peak_bytes: int
    rss_end_bytes: int
    minimum_free_storage_bytes: int
    storage_cycles: int
    storage_bytes_verified: int
    thermal_samples: int
    peak_temperature_celsius: float | None
    injected_crashes: int
    successful_recoveries: int
    failures: tuple[str, ...]
    passed: bool
    contract_version: str = SOAK_CONTRACT_VERSION

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
