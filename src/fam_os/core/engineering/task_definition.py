"""Durable exact task intent for restart-safe engineering orchestration."""

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json

from fam_os.core.engineering._validation import aware, digest, text
from fam_os.core.engineering.authority import EngineeringTaskEnvelope
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class EngineeringTaskDefinition:
    definition_id: str
    task: EngineeringTaskEnvelope
    acceptance_policy_id: str
    created_at: datetime
    task_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.definition_id, "definition_id")
        text(self.acceptance_policy_id, "acceptance_policy_id")
        aware(self.created_at, "created_at")
        digest(self.task_sha256, "task_sha256", required=True)
        if self.task_sha256 != engineering_task_digest(self.task):
            raise ValueError("engineering task definition digest is invalid")
        if self.definition_id != f"definition-{self.task.task_id}":
            raise ValueError("engineering task definition identity is invalid")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering task definition version is unsupported")


def engineering_task_digest(task: EngineeringTaskEnvelope) -> str:
    return hashlib.sha256(
        json.dumps(
            _json_value(asdict(task)), sort_keys=True, separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
