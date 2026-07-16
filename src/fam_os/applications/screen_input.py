"""Provider-neutral contracts for restricted screen and input fallback."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from fam_os.applications.identifiers import require_identifier, require_text


MAX_FRAME_BYTES = 4 * 1024 * 1024
POINT_SCALE = 1_000_000


@dataclass(frozen=True, slots=True)
class ScreenTarget:
    application_id: str
    process_id: int
    window_id: str

    def __post_init__(self) -> None:
        require_identifier(self.application_id, "application_id")
        if self.process_id <= 0:
            raise ValueError("screen target process_id must be positive")
        object.__setattr__(self, "window_id", require_text(self.window_id, "window_id"))

    @property
    def scope(self) -> tuple[str, str]:
        return (f"process:{self.process_id}", f"window:{self.window_id}")


@dataclass(frozen=True, slots=True)
class ScreenFrame:
    captured_at: datetime
    target: ScreenTarget
    source_width: int
    source_height: int
    encoded_width: int
    encoded_height: int
    media_type: str
    image_sha256: str
    encoded_image: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None:
            raise ValueError("screen capture time must be timezone-aware")
        dimensions = (
            self.source_width, self.source_height,
            self.encoded_width, self.encoded_height,
        )
        if min(dimensions) <= 0 or max(dimensions) > 16_384:
            raise ValueError("screen dimensions are invalid")
        if self.media_type != "image/png":
            raise ValueError("screen frame must be PNG")
        if not 0 < len(self.encoded_image) <= MAX_FRAME_BYTES:
            raise ValueError("screen frame byte bound is invalid")
        digest = hashlib.sha256(self.encoded_image).hexdigest()
        if self.image_sha256 != digest:
            raise ValueError("screen frame digest does not match image")

    @property
    def scene_id(self) -> str:
        geometry = f"{self.source_width}x{self.source_height}"
        return f"screen:{self.target.window_id}:{geometry}:{self.image_sha256}"


@dataclass(frozen=True, slots=True)
class ScreenObservation:
    captured_at: datetime
    target: ScreenTarget
    frame: ScreenFrame | None = None
    issue_code: str | None = None

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None:
            raise ValueError("screen observation time must be timezone-aware")
        if (self.frame is None) == (self.issue_code is None):
            raise ValueError("screen observation needs exactly one frame or issue")
        if self.frame is not None and self.frame.target != self.target:
            raise ValueError("screen observation target does not match frame")
        if self.issue_code is not None:
            require_identifier(self.issue_code, "screen issue code")


class ScreenInputKind(StrEnum):
    POINTER_CLICK = "pointer_click"
    KEY_CHORD = "key_chord"


@dataclass(frozen=True, slots=True)
class RelativeScreenPoint:
    x_millionths: int
    y_millionths: int

    def __post_init__(self) -> None:
        if not 0 <= self.x_millionths < POINT_SCALE:
            raise ValueError("relative screen x is invalid")
        if not 0 <= self.y_millionths < POINT_SCALE:
            raise ValueError("relative screen y is invalid")


@dataclass(frozen=True, slots=True)
class ScreenInputInstruction:
    kind: ScreenInputKind
    point: RelativeScreenPoint | None = None
    keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind is ScreenInputKind.POINTER_CLICK:
            if self.point is None or self.keys:
                raise ValueError("pointer click requires only a point")
            return
        if self.kind is ScreenInputKind.KEY_CHORD:
            if self.point is not None or not self.keys or len(self.keys) > 4:
                raise ValueError("key chord requires one to four keys")
            normalized = tuple(require_text(item, "screen key") for item in self.keys)
            if len(set(normalized)) != len(normalized):
                raise ValueError("screen key chord cannot repeat keys")
            if any(len(item) > 32 for item in normalized):
                raise ValueError("screen key name is too long")
            object.__setattr__(self, "keys", normalized)
            return
        raise ValueError("unsupported screen input kind")

    @property
    def digest(self) -> str:
        point = None if self.point is None else {
            "x": self.point.x_millionths, "y": self.point.y_millionths,
        }
        payload = {"kind": self.kind.value, "point": point, "keys": self.keys}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ScreenInputProposal:
    operation_id: str
    target: ScreenTarget
    expected_scene_id: str
    instruction: ScreenInputInstruction
    instruction_digest: str

    def __post_init__(self) -> None:
        require_identifier(self.operation_id, "operation_id")
        require_text(self.expected_scene_id, "expected_scene_id")
        if self.instruction_digest != self.instruction.digest:
            raise ValueError("screen input instruction digest does not match")


@dataclass(frozen=True, slots=True)
class ScreenInputEvidence:
    operation_id: str
    target: ScreenTarget
    instruction_digest: str
    invoked: bool
    before_scene_id: str
    after_scene_id: str | None = None
    issue_code: str | None = None

    def __post_init__(self) -> None:
        require_identifier(self.operation_id, "operation_id")
        require_text(self.before_scene_id, "before_scene_id")
        if len(self.instruction_digest) != 64:
            raise ValueError("screen input digest must be SHA-256")
        if self.after_scene_id is not None:
            require_text(self.after_scene_id, "after_scene_id")
        if self.issue_code is not None:
            require_identifier(self.issue_code, "screen input issue code")
