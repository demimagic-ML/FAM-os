"""Representative design-system and creative-asset documents."""

from fam_os.core.engineering import (
    DesignAssetKind,
    DesignAssetRecord,
    DesignBrief,
    DesignComponent,
    DesignToken,
    DesignVerificationReceipt,
    DesignVerificationStatus,
)
from tests.contract.schema_engineering_fixtures import NOW


def design_schema_values() -> tuple[object, ...]:
    brief = DesignBrief(
        "brief-1", "task-1", "Accessible project console", ("owner",),
        ("Expose task progress",), ("WCAG 2.2 AA",),
        (DesignToken("color.text", "color", "#111111", "Primary text"),),
        (DesignComponent(
            "task-card", ("core.task-graph",),
            ("compact", "wide"), ("keyboard activation",),
            ("4.5:1 contrast", "visible focus"),
        ),),
        ("reference-existing-console",), NOW,
    )
    asset = DesignAssetRecord(
        "asset-1", brief.brief_id, "candidate-1", "assets/task.svg",
        DesignAssetKind.SVG, "image/svg+xml", "a" * 64, (),
        brief.reference_asset_ids, "fam.media.vector", "1.0.0", "b" * 64,
        64, 64, "sRGB", "Apache-2.0", "provenance-1", True, NOW,
    )
    verification = DesignVerificationReceipt(
        "design-verification-1", brief.brief_id, "candidate-1",
        (asset.asset_id,), ("format-1",), ("svg-sanitize-1",),
        ("metadata-1",), ("font-license-1",), ("contrast-1",),
        ("accessibility-1",), ("c" * 64,), 0.01, 0.02,
        "checkpoint-design-1", DesignVerificationStatus.PASSED, NOW,
    )
    return brief, asset, verification
