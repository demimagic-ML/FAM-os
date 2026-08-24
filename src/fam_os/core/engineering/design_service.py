"""Core design orchestration over signed media and deterministic tool ports."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.design import DesignAssetKind, DesignAssetRecord, DesignBrief
from fam_os.registry import PackageTrustLevel
from fam_os.registry.trust_contracts import PackageValidationReport


@dataclass(frozen=True, slots=True)
class GeneratedAssetCandidate:
    content: bytes
    mime_type: str
    tool_id: str
    tool_version: str
    color_profile: str
    license_expression: str
    provenance_id: str


class GenerativeMediaExpert(Protocol):
    @property
    def package_report(self) -> PackageValidationReport: ...

    def generate(self, prompt: str, width: int, height: int, references: tuple[bytes, ...]) -> GeneratedAssetCandidate: ...


class DeterministicAssetTransformer(Protocol):
    def transform(self, content: bytes, mime_type: str, width: int, height: int) -> GeneratedAssetCandidate: ...


class AssetSanitizer(Protocol):
    def sanitize_svg(self, content: bytes): ...

    def sanitize_png(self, content: bytes): ...


class DesignAssetService:
    def __init__(self, sanitizer: AssetSanitizer, clock=None) -> None:
        self._sanitizer = sanitizer
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def generate(
        self,
        brief: DesignBrief,
        candidate_root: Path,
        candidate_id: str,
        relative_path: str,
        prompt: str,
        expert: GenerativeMediaExpert,
        *,
        width: int,
        height: int,
        references: tuple[bytes, ...] = (),
    ) -> DesignAssetRecord:
        report = expert.package_report
        if not report.accepted or report.effective_trust not in {
            PackageTrustLevel.SIGNED, PackageTrustLevel.BUILT_IN,
        }:
            raise PermissionError("generative media expert is not signed and trusted")
        output = expert.generate(prompt, width, height, references)
        return self._persist(
            brief, candidate_root, candidate_id, relative_path, output,
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            source_asset_ids=(), kind=_kind(output.mime_type),
        )

    def derive(
        self,
        brief: DesignBrief,
        candidate_root: Path,
        candidate_id: str,
        relative_path: str,
        source: DesignAssetRecord,
        source_content: bytes,
        transformer: DeterministicAssetTransformer,
        *,
        width: int,
        height: int,
    ) -> DesignAssetRecord:
        output = transformer.transform(source_content, source.mime_type, width, height)
        return self._persist(
            brief, candidate_root, candidate_id, relative_path, output,
            prompt_sha256=None, source_asset_ids=(source.asset_id,),
            kind=_kind(output.mime_type),
        )

    def _persist(self, brief, root, candidate_id, relative, output, *, prompt_sha256, source_asset_ids, kind):
        root = root.resolve(strict=True)
        target = root / relative
        if target.is_symlink() or root not in target.resolve(strict=False).parents:
            raise PermissionError("design asset path escapes candidate workspace")
        sanitized = (
            self._sanitizer.sanitize_svg(output.content)
            if output.mime_type == "image/svg+xml"
            else self._sanitizer.sanitize_png(output.content)
            if output.mime_type == "image/png"
            else None
        )
        if sanitized is None:
            raise ValueError("design asset format lacks a bounded sanitizer")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(sanitized.content)
        return DesignAssetRecord(
            f"design-asset-{uuid4().hex}", brief.brief_id, candidate_id,
            target.relative_to(root).as_posix(), kind, sanitized.mime_type,
            sanitized.sha256, source_asset_ids, brief.reference_asset_ids,
            output.tool_id, output.tool_version, prompt_sha256,
            sanitized.width, sanitized.height, output.color_profile,
            output.license_expression, output.provenance_id, True, self._clock(),
        )


def _kind(mime_type: str) -> DesignAssetKind:
    return DesignAssetKind.SVG if mime_type == "image/svg+xml" else DesignAssetKind.RASTER
