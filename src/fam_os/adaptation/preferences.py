"""Inspectable, owner-bound, atomically resettable preference adapters."""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

PREFERENCE_CONTRACT_VERSION = "fam.adaptation.preferences/v1alpha1"


class PreferenceKey(StrEnum):
    QUALITY_PRIORITY = "quality_priority"
    ENERGY_PRIORITY = "energy_priority"
    LATENCY_PRIORITY = "latency_priority"
    EXPLANATION_DETAIL = "explanation_detail"


@dataclass(frozen=True, slots=True)
class UserPreference:
    key: PreferenceKey
    value: float
    updated_at: datetime

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 1 or self.updated_at.tzinfo is None:
            raise ValueError("preference requires normalized value and aware time")


@dataclass(frozen=True, slots=True)
class UserPreferenceProfile:
    owner_id: str
    preferences: tuple[UserPreference, ...]
    contract_version: str = PREFERENCE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        keys = tuple(item.key for item in self.preferences)
        if not self.owner_id.strip() or len(keys) != len(set(keys)):
            raise ValueError("preference profile requires owner and unique keys")


@dataclass(frozen=True, slots=True)
class PreferenceResetReceipt:
    owner_id: str
    reset_at: datetime
    removed_keys: tuple[PreferenceKey, ...]
    contract_version: str = PREFERENCE_CONTRACT_VERSION


class FilePreferenceStore:
    def __init__(self, path: Path, owner_id: str) -> None:
        self._path, self._owner_id = path, owner_id

    def save(self, profile: UserPreferenceProfile) -> None:
        if profile.owner_id != self._owner_id:
            raise PermissionError("preference owner mismatch")
        payload = asdict(profile)
        payload["preferences"] = [
            {"key": item.key.value, "value": item.value,
             "updated_at": item.updated_at.isoformat()} for item in profile.preferences
        ]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n")
        os.chmod(temporary, 0o600)
        temporary.replace(self._path)

    def inspect(self, owner_id: str) -> UserPreferenceProfile:
        if owner_id != self._owner_id:
            raise PermissionError("preference owner mismatch")
        if not self._path.exists():
            return UserPreferenceProfile(owner_id, ())
        raw = json.loads(self._path.read_text())
        values = tuple(UserPreference(
            PreferenceKey(item["key"]), item["value"], datetime.fromisoformat(item["updated_at"]),
        ) for item in raw["preferences"])
        return UserPreferenceProfile(raw["owner_id"], values)

    def reset(self, owner_id: str, reset_at: datetime) -> PreferenceResetReceipt:
        profile = self.inspect(owner_id)
        self.save(UserPreferenceProfile(owner_id, ()))
        return PreferenceResetReceipt(owner_id, reset_at, tuple(item.key for item in profile.preferences))
