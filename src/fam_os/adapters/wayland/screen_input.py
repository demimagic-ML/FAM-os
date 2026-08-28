"""Exact-window Hyprland capture and controlled-input fallback."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.linux.screen_input.types import (
    ProviderInputAction, ProviderScreenFrame, ProviderWindowState,
)
from fam_os.applications import ScreenInputKind, ScreenTarget


@dataclass(frozen=True, slots=True)
class HyprlandScreenInputSettings:
    session_type: str
    signature_available: bool
    grim_path: str = "grim"
    hyprctl_path: str = "hyprctl"
    wtype_path: str = "wtype"
    ydotool_path: str = "ydotool"


class HyprlandScreenInputProvider:
    """Use compositor identity for capture and explicit Wayland input tools."""

    provider_name = "hyprland-grim-wtype-ydotool"

    def __init__(
        self, settings: HyprlandScreenInputSettings, *, runner=None,
        run_binary: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._settings = settings
        self._runner = runner or SubprocessCommandRunner()
        self._run_binary = run_binary
        self._which = which

    def capture_available(self) -> bool:
        return self._session_available() and self._which(
            self._settings.grim_path,
        ) is not None and self._which(self._settings.hyprctl_path) is not None

    def input_available(self) -> bool:
        return self._session_available() and all(
            self._which(path) is not None for path in (
                self._settings.hyprctl_path, self._settings.wtype_path,
                self._settings.ydotool_path,
            )
        )

    def inspect(self, target: ScreenTarget) -> ProviderWindowState | None:
        if not self._session_available():
            return None
        clients = self._runner.run((self._settings.hyprctl_path, "-j", "clients"))
        active = self._runner.run((self._settings.hyprctl_path, "-j", "activewindow"))
        if clients is None or active is None:
            return None
        try:
            return parse_hyprland_screen_state(target, clients, active)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def capture(
        self, target: ScreenTarget, maximum_source_pixels: int,
        maximum_encoded_pixels: int, maximum_bytes: int,
    ) -> ProviderScreenFrame:
        state = self.inspect(target)
        if state is None or not state.focused:
            raise RuntimeError("Hyprland target is not the active window")
        if state.width * state.height > maximum_source_pixels:
            raise RuntimeError("source window exceeds configured pixel bound")
        geometry = f"{state.x},{state.y} {state.width}x{state.height}"
        executable = self._which(self._settings.grim_path)
        if executable is None:
            raise FileNotFoundError("grim is unavailable")
        result = self._run_binary(
            (executable, "-g", geometry, "-"), check=False,
            capture_output=True, timeout=15,
        )
        image = result.stdout
        if result.returncode != 0 or not isinstance(image, bytes):
            raise RuntimeError("grim capture failed")
        width, height = _png_dimensions(image)
        if width * height > maximum_encoded_pixels or len(image) > maximum_bytes:
            raise RuntimeError("captured PNG exceeds configured bounds")
        return ProviderScreenFrame(state, width, height, image)

    def inject(self, target: ScreenTarget, action: ProviderInputAction) -> bool:
        current = self.inspect(target)
        if current is None or current != action.state or not current.focused:
            return False
        instruction = action.instruction
        if instruction.kind is ScreenInputKind.POINTER_CLICK:
            point = instruction.point
            x = current.x + current.width * point.x_millionths // 1_000_000
            y = current.y + current.height * point.y_millionths // 1_000_000
            if self._runner.run((
                self._settings.hyprctl_path, "dispatch", "movecursor", str(x), str(y),
            )) is None:
                return False
            return self._command((self._settings.ydotool_path, "click", "0xC0"))
        if instruction.kind is ScreenInputKind.KEY_CHORD:
            return self._command(_wtype_chord(
                self._settings.wtype_path, instruction.keys,
            ))
        return False

    def _session_available(self) -> bool:
        return (
            self._settings.session_type.casefold() == "wayland"
            and self._settings.signature_available
        )

    def _command(self, command: tuple[str, ...]) -> bool:
        executable = self._which(command[0])
        if executable is None:
            return False
        result = self._run_binary(
            (executable, *command[1:]), check=False, capture_output=True,
            text=True, timeout=10,
        )
        return result.returncode == 0


def parse_hyprland_screen_state(
    target: ScreenTarget, clients_json: str, active_json: str,
) -> ProviderWindowState | None:
    clients = json.loads(clients_json)
    active = json.loads(active_json)
    if not isinstance(clients, list) or not isinstance(active, dict):
        raise ValueError("Hyprland screen state must contain clients and active window")
    active_address = _address(active.get("address"))
    for item in clients:
        if not isinstance(item, dict) or _address(item.get("address")) != target.window_id:
            continue
        at, size, process_id = item.get("at"), item.get("size"), item.get("pid")
        if not (
            isinstance(at, list) and len(at) == 2
            and isinstance(size, list) and len(size) == 2
            and all(isinstance(value, int) for value in at + size)
            and isinstance(process_id, int)
            and process_id == target.process_id
        ):
            return None
        return ProviderWindowState(
            target.window_id, process_id, at[0], at[1], size[0], size[1],
            active_address == target.window_id,
        )
    return None


def _address(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.casefold()
    if not normalized.startswith("0x"):
        normalized = "0x" + normalized
    return normalized


def _png_dimensions(image: bytes) -> tuple[int, int]:
    if len(image) < 24 or not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("grim did not return a PNG")
    width = int.from_bytes(image[16:20], "big")
    height = int.from_bytes(image[20:24], "big")
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions are invalid")
    return width, height


def _wtype_chord(executable: str, keys: tuple[str, ...]) -> tuple[str, ...]:
    modifiers = {
        "Control_L": "ctrl", "Control_R": "ctrl", "Shift_L": "shift",
        "Shift_R": "shift", "Alt_L": "alt", "Alt_R": "alt",
        "Super_L": "logo", "Super_R": "logo",
    }
    held = [modifiers[key] for key in keys if key in modifiers]
    pressed = [key for key in keys if key not in modifiers]
    command = [executable]
    for modifier in held:
        command.extend(("-M", modifier))
    for key in pressed:
        command.extend(("-k", key))
    for modifier in reversed(held):
        command.extend(("-m", modifier))
    return tuple(command)


def default_hyprland_screen_input_provider() -> HyprlandScreenInputProvider:
    return HyprlandScreenInputProvider(HyprlandScreenInputSettings(
        os.environ.get("XDG_SESSION_TYPE", "unknown"),
        bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")),
    ))
