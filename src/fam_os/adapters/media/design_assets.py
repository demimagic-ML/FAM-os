"""Bounded deterministic SVG and PNG validation/sanitization adapters."""

import binascii
import hashlib
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SanitizedAsset:
    content: bytes
    width: int
    height: int
    mime_type: str
    sha256: str
    removed_metadata: tuple[str, ...]


class DesignAssetSanitizer:
    def __init__(self, *, maximum_input_bytes: int = 20 * 1024**2, maximum_pixels: int = 40_000_000) -> None:
        self._maximum_input = maximum_input_bytes
        self._maximum_pixels = maximum_pixels

    def sanitize_svg(self, content: bytes) -> SanitizedAsset:
        if len(content) > self._maximum_input or b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
            raise ValueError("SVG input is unsafe or exceeds its bound")
        root = ET.fromstring(content)
        if _local(root.tag) != "svg":
            raise ValueError("SVG root element is required")
        count = 0
        removed = []
        for element in root.iter():
            count += 1
            if count > 20_000 or _local(element.tag) in {"script", "foreignObject"}:
                raise ValueError("SVG contains an unsafe or excessive element tree")
            for name in tuple(element.attrib):
                value = element.attrib[name].strip()
                local = _local(name).lower()
                if local.startswith("on") or local in {"href", "src"} and not value.startswith("#"):
                    raise ValueError("SVG contains executable or external content")
                if local in {"metadata", "data-author", "data-generator"}:
                    removed.append(local)
                    del element.attrib[name]
        width = _dimension(root.attrib.get("width"), 1)
        height = _dimension(root.attrib.get("height"), 1)
        _pixels(width, height, self._maximum_pixels)
        result = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        return SanitizedAsset(result, width, height, "image/svg+xml", hashlib.sha256(result).hexdigest(), tuple(sorted(set(removed))))

    def sanitize_png(self, content: bytes) -> SanitizedAsset:
        if len(content) > self._maximum_input or not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PNG input is invalid or exceeds its bound")
        position = 8
        output = bytearray(content[:8])
        width = height = 0
        removed = []
        while position < len(content):
            if position + 12 > len(content):
                raise ValueError("PNG chunk is truncated")
            length = struct.unpack(">I", content[position:position + 4])[0]
            if length > self._maximum_input or position + 12 + length > len(content):
                raise ValueError("PNG chunk exceeds its declared bounds")
            kind = content[position + 4:position + 8]
            data = content[position + 8:position + 8 + length]
            crc = content[position + 8 + length:position + 12 + length]
            if binascii.crc32(kind + data).to_bytes(4, "big") != crc:
                raise ValueError("PNG chunk checksum is invalid")
            if kind == b"IHDR":
                width, height = struct.unpack(">II", data[:8])
                _pixels(width, height, self._maximum_pixels)
            if kind in {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS"}:
                output.extend(content[position:position + 12 + length])
            else:
                removed.append(kind.decode("ascii", errors="replace"))
            position += 12 + length
            if kind == b"IEND":
                break
        if not width or not height or not output.endswith(b"IEND\xaeB`\x82"):
            raise ValueError("PNG is missing mandatory structure")
        result = bytes(output)
        return SanitizedAsset(result, width, height, "image/png", hashlib.sha256(result).hexdigest(), tuple(sorted(set(removed))))


def contrast_ratio(foreground: str, background: str) -> float:
    first, second = (_luminance(_rgb(value)) for value in (foreground, background))
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def visual_difference(left: bytes, right: bytes) -> float:
    size = max(len(left), len(right))
    if size == 0:
        return 0.0
    mismatches = sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))
    return mismatches / size


def _local(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def _dimension(value: str | None, default: int) -> int:
    if value is None:
        return default
    cleaned = value.removesuffix("px")
    if not cleaned.isdigit():
        raise ValueError("asset dimension must be an integer pixel value")
    return int(cleaned)


def _pixels(width: int, height: int, maximum: int) -> None:
    if width <= 0 or height <= 0 or width * height > maximum:
        raise ValueError("asset decompression dimensions exceed policy")


def _rgb(value: str) -> tuple[int, int, int]:
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError("color must use #RRGGBB")
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def _luminance(rgb: tuple[int, int, int]) -> float:
    values = tuple(component / 255 for component in rgb)
    linear = tuple(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
