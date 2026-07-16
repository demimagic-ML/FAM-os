"""X11 composition for exact active-window capture and XTest input."""

from fam_os.adapters.linux.screen_input.pillow_capture import PillowPngCapture
from fam_os.adapters.linux.screen_input.types import ProviderScreenFrame
from fam_os.adapters.linux.screen_input.x11_inspector import (
    X11InspectorSettings, X11WindowInspector,
)
from fam_os.adapters.linux.screen_input.xtest_input import XTestInput
from fam_os.applications import ScreenInputKind


class X11ScreenInputProvider:
    def __init__(self, settings: X11InspectorSettings, inspector=None, capture=None, input=None):
        self._inspector = inspector or X11WindowInspector(settings)
        self._capture = capture or PillowPngCapture(settings.display)
        self._input = input or XTestInput(settings.display)

    def capture_available(self) -> bool:
        return self._inspector.available() and self._capture.available()

    def input_available(self) -> bool:
        return self._inspector.available() and self._input.available()

    def inspect(self, target):
        return self._inspector.inspect(target)

    def capture(self, target, maximum_source_pixels, maximum_pixels, maximum_bytes):
        state = self._inspector.inspect(target)
        if state is None or not _matches(target, state) or not state.focused:
            raise RuntimeError("X11 target is not the active window")
        width, height, encoded = self._capture.grab(
            state, maximum_source_pixels, maximum_pixels, maximum_bytes,
        )
        return ProviderScreenFrame(state, width, height, encoded)

    def inject(self, target, action):
        current = self._inspector.inspect(target)
        if current is None or not _matches(target, current):
            return False
        if current != action.state or not current.focused:
            return False
        instruction = action.instruction
        if instruction.kind is ScreenInputKind.POINTER_CLICK:
            point = instruction.point
            x = current.x + current.width * point.x_millionths // 1_000_000
            y = current.y + current.height * point.y_millionths // 1_000_000
            return self._input.click(x, y)
        if instruction.kind is ScreenInputKind.KEY_CHORD:
            return self._input.key_chord(instruction.keys)
        return False


def _matches(target, state):
    return state.window_id == target.window_id and state.process_id == target.process_id
