"""Provider-owned screen and input values."""

from dataclasses import dataclass, field

from fam_os.applications import ScreenInputInstruction


@dataclass(frozen=True, slots=True)
class ProviderWindowState:
    window_id: str
    process_id: int
    x: int
    y: int
    width: int
    height: int
    focused: bool

    def __post_init__(self) -> None:
        if self.process_id <= 0 or min(self.width, self.height) <= 0:
            raise ValueError("provider window state is invalid")


@dataclass(frozen=True, slots=True)
class ProviderScreenFrame:
    state: ProviderWindowState
    encoded_width: int
    encoded_height: int
    encoded_png: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if min(self.encoded_width, self.encoded_height) <= 0:
            raise ValueError("provider frame dimensions are invalid")
        if not self.encoded_png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("provider frame is not PNG")


@dataclass(frozen=True, slots=True)
class ProviderInputAction:
    state: ProviderWindowState
    instruction: ScreenInputInstruction
