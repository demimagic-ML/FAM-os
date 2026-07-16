"""Defensive GI-backed AT-SPI provider for the Linux accessibility bridge."""

import warnings

from fam_os.adapters.linux.accessibility.types import (
    ProviderAccessibleAction,
    ProviderAccessibleNode,
)


class GiAtspiProvider:
    """Keep GI objects and failures behind the provider-neutral bridge port."""

    def __init__(self) -> None:
        self._atspi = _load_atspi()

    def available(self) -> bool:
        if self._atspi is None:
            return False
        try:
            return self._atspi.get_desktop_count() > 0
        except Exception:
            return False

    def roots(self) -> tuple[object, ...]:
        if not self.available():
            return ()
        roots = []
        try:
            desktop_count = min(self._atspi.get_desktop_count(), 8)
            for desktop_index in range(desktop_count):
                desktop = self._atspi.get_desktop(desktop_index)
                count = min(_integer(desktop.get_child_count()), 512)
                for child_index in range(count):
                    child = desktop.get_child_at_index(child_index)
                    if child is not None:
                        roots.append(child)
        except Exception:
            return tuple(roots)
        return tuple(roots)

    def read(
        self, handle, maximum_text_characters: int, include_text: bool = False,
    ) -> ProviderAccessibleNode:
        role = _text(handle.get_role_name(), "unknown", 128)
        protected = self._protected(handle, role)
        actions = () if protected else self._actions(handle)
        text, text_truncated = (None, False)
        if include_text and not protected:
            text, text_truncated = self._text(handle, maximum_text_characters)
        return ProviderAccessibleNode(
            process_id=_integer(handle.get_process_id()),
            role=role,
            name=None if protected else _optional_text(handle.get_name(), 1024),
            description=None if protected else _optional_text(handle.get_description(), 1024),
            states=self._states(handle),
            actions=actions,
            text=text,
            protected=protected,
            child_count=max(0, _integer(handle.get_child_count())),
            text_truncated=text_truncated,
        )

    def child(self, handle, index: int) -> object | None:
        try:
            return handle.get_child_at_index(index)
        except Exception:
            return None

    def perform_action(self, handle, action_index: int) -> bool:
        try:
            return bool(handle.do_action(action_index))
        except Exception:
            return False

    def _actions(self, handle) -> tuple[ProviderAccessibleAction, ...]:
        try:
            count = min(max(0, _integer(handle.get_n_actions())), 64)
            with warnings.catch_warnings():
                # Current GI metadata warns for the replacement Action methods too.
                warnings.simplefilter("ignore", DeprecationWarning)
                return tuple(
                    ProviderAccessibleAction(
                        index,
                        _text(handle.get_action_name(index), "unknown", 128),
                        _optional_text(handle.get_action_description(index), 512),
                        _optional_text(handle.get_key_binding(index), 256),
                    )
                    for index in range(count)
                )
        except Exception:
            return ()

    def _states(self, handle) -> tuple[str, ...]:
        try:
            values = handle.get_state_set().get_states()
            names = (_text(getattr(item, "value_nick", str(item)), "unknown", 128) for item in values)
            return tuple(sorted(set(names)))
        except Exception:
            return ()

    def _text(self, handle, maximum: int) -> tuple[str | None, bool]:
        try:
            if "Text" not in tuple(handle.get_interfaces()):
                return None, False
            count = max(0, _integer(handle.get_character_count()))
            limit = min(count, maximum)
            value = handle.get_text(0, limit) if limit else ""
            return _optional_text(value, maximum), count > limit
        except Exception:
            return None, False

    def _protected(self, handle, role: str) -> bool:
        try:
            return handle.get_role() == self._atspi.Role.PASSWORD_TEXT
        except Exception:
            return role.casefold() in {"password text", "password_text"}


def _load_atspi():
    try:
        import gi

        gi.require_version("Atspi", "2.0")
        from gi.repository import Atspi

        return Atspi
    except (ImportError, ValueError):
        return None


def _integer(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value, fallback: str, maximum: int) -> str:
    normalized = str(value or "").strip()
    return (normalized or fallback)[:maximum]


def _optional_text(value, maximum: int) -> str | None:
    normalized = str(value or "").strip()
    return normalized[:maximum] if normalized else None
