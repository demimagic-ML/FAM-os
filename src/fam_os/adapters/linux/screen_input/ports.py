"""Ports isolating desktop capture and input providers."""

from typing import Protocol

from fam_os.adapters.linux.screen_input.types import (
    ProviderInputAction, ProviderScreenFrame, ProviderWindowState,
)
from fam_os.applications import ScreenTarget


class ScreenInputProvider(Protocol):
    def capture_available(self) -> bool: ...

    def input_available(self) -> bool: ...

    def inspect(self, target: ScreenTarget) -> ProviderWindowState | None: ...

    def capture(
        self, target: ScreenTarget, maximum_source_pixels: int,
        maximum_encoded_pixels: int, maximum_bytes: int,
    ) -> ProviderScreenFrame: ...

    def inject(self, target: ScreenTarget, action: ProviderInputAction) -> bool: ...
