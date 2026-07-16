"""Minimal XTest pointer and key injector with no generic X11 surface."""

import ctypes
import ctypes.util


class XTestInput:
    def __init__(self, display: str):
        self._display = display.encode()

    def available(self) -> bool:
        try:
            x11, xtst = _libraries()
            display = x11.XOpenDisplay(self._display)
            if not display:
                return False
            try:
                values = (ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_int())
                return bool(xtst.XTestQueryExtension(
                    display, *(ctypes.byref(value) for value in values)
                ))
            finally:
                x11.XCloseDisplay(display)
        except Exception:
            return False

    def click(self, x: int, y: int) -> bool:
        def operation(x11, xtst, display):
            moved = xtst.XTestFakeMotionEvent(display, -1, x, y, 0)
            down = xtst.XTestFakeButtonEvent(display, 1, True, 0)
            up = xtst.XTestFakeButtonEvent(display, 1, False, 0)
            return bool(moved and down and up)
        return self._with_display(operation)

    def key_chord(self, keys: tuple[str, ...]) -> bool:
        def operation(x11, xtst, display):
            codes = tuple(_keycode(x11, display, key) for key in keys)
            if any(code == 0 for code in codes):
                return False
            results = [xtst.XTestFakeKeyEvent(display, code, True, 0) for code in codes]
            results += [xtst.XTestFakeKeyEvent(display, code, False, 0) for code in reversed(codes)]
            return all(results)
        return self._with_display(operation)

    def _with_display(self, operation):
        x11, xtst = _libraries()
        display = x11.XOpenDisplay(self._display)
        if not display:
            return False
        try:
            succeeded = operation(x11, xtst, display)
            x11.XFlush(display)
            return succeeded
        finally:
            x11.XCloseDisplay(display)


def _keycode(x11, display, key):
    keysym = x11.XStringToKeysym(key.encode())
    return x11.XKeysymToKeycode(display, keysym) if keysym else 0


def _libraries():
    x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
    xtst = ctypes.CDLL(ctypes.util.find_library("Xtst") or "libXtst.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.restype = ctypes.c_int
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x11.XStringToKeysym.restype = ctypes.c_ulong
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x11.XKeysymToKeycode.restype = ctypes.c_uint
    x11.XFlush.argtypes = [ctypes.c_void_p]
    x11.XFlush.restype = ctypes.c_int
    xtst.XTestFakeMotionEvent.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong,
    ]
    xtst.XTestFakeButtonEvent.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong,
    ]
    xtst.XTestFakeKeyEvent.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong,
    ]
    xtst.XTestQueryExtension.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
    ]
    xtst.XTestQueryExtension.restype = ctypes.c_int
    for function in (
        xtst.XTestFakeMotionEvent, xtst.XTestFakeButtonEvent, xtst.XTestFakeKeyEvent,
    ):
        function.restype = ctypes.c_int
    return x11, xtst
