# Handoff 0196: Verified design and creative assets

**Date:** 2026-07-18  
**Plan step:** Phase 28  
**Status:** Complete  
**Previous handoff:** `0195-complete-polyglot-dependency-and-privilege-layer.md`

## Objective

Make UI systems and creative media first-class provenance-bound candidate
artifacts with deterministic safety and review gates.

## Scope completed

- Added typed briefs, tokens, component inventories, responsive/interaction
  states, accessibility requirements, and architecture traceability.
- Added signed-expert generation and deterministic derived-asset services.
- Added SVG active-content rejection, PNG CRC and metadata stripping, pixel
  limits, contrast and visual-difference checks.
- Added network-denied fresh-profile responsive browser captures.
- Built, captured, applied, and fully restored an accessible web design fixture.

## Explicitly not completed

- Phase 31 long-running creative parser pressure and independent review.

## Architecture and decisions

ADR 0171 makes candidate sanitization and human preview invariant for published
creative assets. Models never write owner assets directly.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/engineering/design.py` | Design and provenance contracts |
| `src/fam_os/core/engineering/design_service.py` | Signed generation and derivation |
| `src/fam_os/adapters/media/design_assets.py` | SVG/PNG/contrast/visual checks |
| `src/fam_os/adapters/media/browser_capture.py` | Responsive local browser evidence |
| `tests/integration/test_design_system_exit.py` | Apply/capture/restore exit fixture |

## Public interfaces

`DesignBrief`, `DesignAssetRecord`, `DesignVerificationReceipt`,
`DesignAssetService`, `GeneratedAssetCandidate`, `DesignAssetSanitizer`, and
`LocalResponsiveBrowserCapture`.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.unit.test_design_assets tests.integration.test_design_system_exit -v
```

Result: five design tests pass, including real 360x640 and 1280x720 Chrome
captures and complete journal restoration.

## Evidence and artifacts

- `docs/decisions/0171-design-assets-are-provenance-bound-sanitized-candidates.md`
- Installed suite evidence in `artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt2.json`

## Known limitations and risks

- Initial bounded in-process sanitizers accept SVG and PNG; other formats need
  separately qualified deterministic adapters.

## Operational notes

Browser profiles are temporary and external name resolution is denied.

## Recommended next entry point

Read ADR 0172 and Handoff 0197, then inspect Git publication approval.
