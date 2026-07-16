"""Provider port isolating GI/AT-SPI object handles from the bridge."""

from typing import Protocol

from fam_os.adapters.linux.accessibility.types import ProviderAccessibleNode


class AccessibilityProvider(Protocol):
    def available(self) -> bool: ...

    def roots(self) -> tuple[object, ...]: ...

    def read(
        self, handle: object, maximum_text_characters: int, include_text: bool = False,
    ) -> ProviderAccessibleNode: ...

    def child(self, handle: object, index: int) -> object | None: ...

    def perform_action(self, handle: object, action_index: int) -> bool: ...
