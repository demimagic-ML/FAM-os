import binascii
import struct
import unittest
import zlib
import tempfile
from pathlib import Path

from fam_os.adapters.media.design_assets import (
    DesignAssetSanitizer,
    contrast_ratio,
    visual_difference,
)
from fam_os.core.engineering import DesignAssetService, GeneratedAssetCandidate
from fam_os.registry import ArtifactDigest, PackageTrustLevel
from fam_os.registry.trust_contracts import PackageValidationReport
from tests.contract.schema_design_fixtures import design_schema_values


def _chunk(kind, value):
    return struct.pack(">I", len(value)) + kind + value + binascii.crc32(kind + value).to_bytes(4, "big")


def _png(metadata=True):
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    scanline = zlib.compress(b"\0\xff\xff\xff")
    chunks = [_chunk(b"IHDR", header)]
    if metadata:
        chunks.append(_chunk(b"tEXt", b"Author\0untrusted"))
    chunks.extend((_chunk(b"IDAT", scanline), _chunk(b"IEND", b"")))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


class DesignAssetTests(unittest.TestCase):
    def test_svg_sanitization_rejects_script_external_refs_and_excessive_dimensions(self):
        sanitizer = DesignAssetSanitizer(maximum_pixels=10_000)
        safe = sanitizer.sanitize_svg(
            b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><path d="M0 0h2v2z"/></svg>'
        )
        self.assertEqual((20, 20), (safe.width, safe.height))
        for unsafe in (
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>bad()</script></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil/x"/></svg>',
            b'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000"/>',
        ):
            with self.assertRaises(ValueError):
                sanitizer.sanitize_svg(unsafe)

    def test_png_metadata_is_removed_without_reencoding_pixels(self):
        result = DesignAssetSanitizer().sanitize_png(_png())
        self.assertEqual((1, 1), (result.width, result.height))
        self.assertEqual(("tEXt",), result.removed_metadata)
        self.assertNotIn(b"Author", result.content)
        self.assertEqual(result.content, DesignAssetSanitizer().sanitize_png(result.content).content)

    def test_contrast_and_visual_threshold_measurements_are_deterministic(self):
        self.assertGreater(contrast_ratio("#111111", "#ffffff"), 4.5)
        self.assertEqual(0.25, visual_difference(b"abcd", b"abXd"))

    def test_generation_requires_signed_expert_and_writes_only_sanitized_candidate(self):
        brief = design_schema_values()[0]
        trusted = _MediaExpert(PackageTrustLevel.SIGNED)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            record = DesignAssetService(DesignAssetSanitizer()).generate(
                brief, root, "candidate-1", "assets/generated.svg",
                "draw a bounded icon", trusted, width=20, height=20,
            )
            self.assertTrue((root / record.relative_path).is_file())
            self.assertEqual("fam.media.fixture", record.model_or_tool_id)
            self.assertTrue(record.metadata_stripped)
            with self.assertRaisesRegex(PermissionError, "not signed"):
                DesignAssetService(DesignAssetSanitizer()).generate(
                    brief, root, "candidate-1", "assets/unsafe.svg", "bad",
                    _MediaExpert(PackageTrustLevel.LOCAL_UNVERIFIED),
                    width=20, height=20,
                )


class _MediaExpert:
    def __init__(self, trust):
        self._report = PackageValidationReport(
            "fam.media.fixture", "1.0.0", True, "accepted", trust,
            ArtifactDigest("sha256", "a" * 64), "design-policy-1",
            "release-key" if trust is PackageTrustLevel.SIGNED else None,
        )

    @property
    def package_report(self):
        return self._report

    def generate(self, prompt, width, height, references):
        return GeneratedAssetCandidate(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="20" height="20"/></svg>'.encode(),
            "image/svg+xml", "fam.media.fixture", "1.0.0", "sRGB",
            "Apache-2.0", "generation-1",
        )


if __name__ == "__main__":
    unittest.main()
