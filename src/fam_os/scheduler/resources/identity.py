"""Named validation-profile identity contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


COMPAT_CPU_16GB_PROFILE_ID = "compat-cpu-16gb"
FULL_REFERENCE_WORKSTATION_PROFILE_ID = "full-reference-workstation"


class ValidationProfilePurpose(str, Enum):
    """Why a resource profile exists, independent of its concrete limits."""

    MINIMUM_COMPATIBILITY = "minimum_compatibility"
    FULL_HOST_CAPABILITY = "full_host_capability"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class ValidationProfileRef:
    """Stable identity and purpose for the profile that produced a budget."""

    profile_id: str
    purpose: ValidationProfilePurpose

    def __post_init__(self) -> None:
        profile_id = self.profile_id.strip()
        if not profile_id:
            raise ValueError("profile_id must not be empty")
        expected = {
            COMPAT_CPU_16GB_PROFILE_ID: ValidationProfilePurpose.MINIMUM_COMPATIBILITY,
            FULL_REFERENCE_WORKSTATION_PROFILE_ID: ValidationProfilePurpose.FULL_HOST_CAPABILITY,
        }.get(profile_id)
        if expected is not None and self.purpose is not expected:
            raise ValueError(f"{profile_id} must use purpose {expected.value}")
        if expected is None and self.purpose is not ValidationProfilePurpose.CUSTOM:
            raise ValueError("non-reserved profile IDs must use the custom purpose")
