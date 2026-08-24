# ADR 0171: Design assets are provenance-bound sanitized candidates

Status: Accepted

## Context

Creative models and file formats add active-content, metadata, decompression,
licensing, accessibility, and review risks beyond ordinary source text.

## Decision

Design work uses strict briefs, tokens, component and responsive inventories,
interaction/accessibility requirements, and architecture traceability. A
generative model may produce bytes only through a signed expert package. Core
then routes those bytes through deterministic bounded sanitizers before writing
the candidate workspace. Every asset record binds its brief, references,
source/derived lineage, tool identity/version, prompt digest, dimensions, color
profile, license, provenance, sanitized digest, and human checkpoint.

SVG rejects entities, scripts, foreign objects, event handlers, and external
references. PNG validation checks structure, CRCs, pixel limits, and strips
ancillary metadata without re-encoding pixels. Responsive browser captures use
a fresh profile, local file input, denied external name resolution, explicit
viewport bounds, and content digests. Contrast, accessibility, visual threshold,
font/license, format, and human preview evidence are required before pass.

## Consequences

- Model output never becomes a published design asset directly.
- Creative edits use the same candidate, checkpoint, journal, and rollback path
  as source changes.
- Unsupported media formats fail closed until a bounded sanitizer exists.
- A visual regression above threshold cannot be labeled passed.

## Evidence

- `src/fam_os/core/engineering/design.py`
- `src/fam_os/core/engineering/design_service.py`
- `src/fam_os/adapters/media/design_assets.py`
- `src/fam_os/adapters/media/browser_capture.py`
- `tests/integration/test_design_system_exit.py`

## Superseded decisions

None.
