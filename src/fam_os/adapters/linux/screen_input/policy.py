"""Conservative bounds for the last-resort desktop adapter."""

from dataclasses import dataclass

from fam_os.applications import ScreenInputKind


DEFAULT_KEYS = (
    "BackSpace", "Down", "End", "Escape", "Home", "Left", "Next", "Prior",
    "Return", "Right", "Tab", "Up", "Control_L", "Shift_L", "z",
)


@dataclass(frozen=True, slots=True)
class ScreenInputPolicy:
    maximum_source_pixels: int = 16_000_000
    maximum_encoded_pixels: int = 2_000_000
    maximum_encoded_bytes: int = 4 * 1024 * 1024
    require_focused_window: bool = True
    allowed_kinds: tuple[ScreenInputKind, ...] = (
        ScreenInputKind.POINTER_CLICK, ScreenInputKind.KEY_CHORD,
    )
    allowed_keys: tuple[str, ...] = DEFAULT_KEYS

    def __post_init__(self) -> None:
        if min(self.maximum_source_pixels, self.maximum_encoded_pixels) <= 0:
            raise ValueError("screen capture pixel bounds are invalid")
        if self.maximum_encoded_pixels > self.maximum_source_pixels:
            raise ValueError("encoded screen pixels cannot exceed source bound")
        if not 0 < self.maximum_encoded_bytes <= 4 * 1024 * 1024:
            raise ValueError("screen capture bounds are invalid")
        if not self.allowed_kinds or len(set(self.allowed_kinds)) != len(self.allowed_kinds):
            raise ValueError("screen input kinds must be unique")
        if not self.allowed_keys or any(not key for key in self.allowed_keys):
            raise ValueError("screen input keys cannot be empty")
        if len(set(self.allowed_keys)) != len(self.allowed_keys):
            raise ValueError("screen input keys must be unique")
