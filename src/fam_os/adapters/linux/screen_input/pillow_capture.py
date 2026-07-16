"""Optional Pillow-backed bounded PNG capture."""

import io
import math

from fam_os.adapters.linux.screen_input.types import ProviderWindowState


class PillowPngCapture:
    def __init__(self, display: str):
        self._display = display

    def available(self) -> bool:
        try:
            from PIL import ImageGrab  # noqa: F401
        except Exception:
            return False
        return bool(self._display)

    def grab(
        self, state: ProviderWindowState, maximum_source_pixels: int,
        maximum_pixels: int, maximum_bytes: int,
    ):
        from PIL import Image, ImageGrab

        if state.width * state.height > maximum_source_pixels:
            raise RuntimeError("source window exceeds configured pixel bound")
        image = ImageGrab.grab(
            bbox=(state.x, state.y, state.x + state.width, state.y + state.height),
            xdisplay=self._display,
        ).convert("RGB")
        image = _fit_pixels(image, maximum_pixels, Image.Resampling.LANCZOS)
        for _ in range(5):
            encoded = _encode(image)
            if len(encoded) <= maximum_bytes:
                return image.width, image.height, encoded
            image.thumbnail(
                (max(1, image.width * 3 // 4), max(1, image.height * 3 // 4)),
                Image.Resampling.LANCZOS,
            )
        raise RuntimeError("PNG capture exceeds configured byte bound")


def _fit_pixels(image, maximum_pixels, resampling):
    pixels = image.width * image.height
    if pixels <= maximum_pixels:
        return image
    scale = math.sqrt(maximum_pixels / pixels)
    image.thumbnail(
        (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
        resampling,
    )
    return image


def _encode(image):
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=6)
    return output.getvalue()
