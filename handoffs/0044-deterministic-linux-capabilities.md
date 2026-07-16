# Handoff 0044: Deterministic Linux capabilities

**Date:** 2026-07-16  
**Plan step:** Phase 5.6  
**Status:** Complete  
**Previous handoff:** `0043-linux-application-discovery.md`

## Objective

Implement scoped file, MIME, D-Bus, desktop-portal, and explicit tool
capabilities as exact Application Fabric level-2 adapters without adding a
general shell or overstating raw execution as verified success.

## Scope completed

- Absolute-executable, explicit-environment, shell-free bounded process runner.
- Scoped regular-file observation with opt-in content and SHA-256 evidence.
- Proposal/current-hash/content-bound atomic file replacement and post-hash check.
- Magic MIME detection with labeled extension fallback.
- Exact allowlisted primitive D-Bus bus/destination/path/interface/member calls.
- Prepared allowlisted desktop-portal OpenURI plus read-only availability probe.
- Exact fixed tool/parameter mappings with text/JSON normalized output.
- OS-tool connector declarations and conservative irreversible action policy.
- Live-safe file/MIME/sha256/D-Bus/portal probes.

## Explicitly not completed

- General shell, arbitrary executable/argument arrays, inherited environment, or
  unbounded subprocess output.
- D-Bus container signatures.
- Durable file undo/reversal or hostile-race-hardened openat2 path traversal.
- Live portal OpenURI or user-file mutation tests.
- Core confirmation/postcondition/audit composition (Phase 5.11).

## Architecture and decisions

ADR 0044 uses one process transport and separate adapters. File writes are
two-stage, atomic, revision/content-bound, and declared irreversible/always
confirmed until real undo exists. D-Bus/tool/portal failures discard provider
stderr. Every adapter returns raw evidence; only Core can release verified action
success.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/adapters/linux/bounded_command.py` | Time/output/process-group bounded transport. |
| `src/fam_os/adapters/linux/scoped_files.py` | Scoped observation and atomic write. |
| `src/fam_os/adapters/linux/mime_types.py` | MIME evidence and fallback provenance. |
| `src/fam_os/adapters/linux/dbus_calls.py` | Primitive exact D-Bus calls. |
| `src/fam_os/adapters/linux/desktop_portal.py` | Prepared OpenURI and availability probe. |
| `src/fam_os/adapters/linux/tools.py` | Explicit deterministic tool mappings. |
| `src/fam_os/adapters/linux/deterministic_catalog.py` | OS-tool capability registration. |
| `src/fam_os/adapters/linux/deterministic_result.py` | Content-safe raw result. |
| `tests/unit/test_bounded_command_runner.py` | Shell/time/output tests. |
| `tests/unit/test_scoped_file_adapter.py` | Scope/hash/atomicity tests. |
| `tests/unit/test_mime_type_adapter.py` | Magic/fallback tests. |
| `tests/unit/test_deterministic_linux_capabilities.py` | D-Bus/tool/portal tests. |
| `tests/unit/test_deterministic_capability_catalog.py` | Registry policy tests. |
| `tests/integration/test_deterministic_linux_capabilities_live.py` | Live-safe proof. |
| `tests/architecture/test_deterministic_linux_capability_boundary.py` | Layer/spawn guard. |
| `docs/protocols/DETERMINISTIC_LINUX_CAPABILITIES.md` | Protocol and limitations. |
| `docs/decisions/0044-allowlisted-shell-free-linux-capabilities.md` | Durable decision. |

## Public interfaces

- `BoundedCommandPolicy`, `BoundedCommandResult`, `BoundedSubprocessRunner`.
- `ScopedFilePolicy`, `ScopedFileAdapter`, proposal/observation/evidence values.
- `ScopedMimeTypeAdapter` and `MimeTypeEvidence`.
- `DbusCapabilitySpec`, primitive parameters, and `AllowlistedDbusAdapter`.
- `PortalOpenUriPolicy`, `PortalOpenProposal`, and `DesktopPortalAdapter`.
- `ToolCapabilitySpec`, parameters/output kind, and `AllowlistedToolAdapter`.
- Deterministic capability declarations and registration builder.

## Validation

```bash
PYTHONPATH=src:. python3 -W error::ResourceWarning -m unittest tests.unit.test_bounded_command_runner tests.unit.test_scoped_file_adapter tests.unit.test_mime_type_adapter tests.unit.test_deterministic_linux_capabilities tests.unit.test_deterministic_capability_catalog tests.architecture.test_deterministic_linux_capability_boundary tests.integration.test_deterministic_linux_capabilities_live
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
python3 <AST module/function size gate>
larry index . && larry health .
```

Result: 16 focused/live tests and all 477 repository tests passed in the MCP
environment; system Python passed 477 with two MCP-only live skips. All 35
schemas matched and compile/AST gates passed. Larry indexed 634 files / 1,885
symbols with 8,443 nodes / 30,728 edges and clean health; the persisted graph
was refreshed with the same totals.

## Evidence and artifacts

- `docs/protocols/DETERMINISTIC_LINUX_CAPABILITIES.md`
- `docs/decisions/0044-allowlisted-shell-free-linux-capabilities.md`
- `tests/integration/test_deterministic_linux_capabilities_live.py`

## Known limitations and risks

- Path checks use path APIs plus final `O_NOFOLLOW`; a same-user hostile race in
  intermediate directories needs openat2/dirfd hardening.
- Atomic replacement has no durable backup, so it is intentionally irreversible.
- Portal acceptance and D-Bus/tool exit zero are not application postconditions.

## Operational notes

Live validation read one temporary file, invoked `file` and `sha256sum`, pinged
the user D-Bus daemon, and read the portal OpenURI version. It did not open a URI,
write user data, launch an app, or alter desktop state.

## Recommended next entry point

Begin Phase 5.7. Define bounded AT-SPI object identity/tree/text/action values,
an SDK/provider port, protected-content rules, stale-object revalidation, and
separate observe/action adapters. Verify graceful degradation when the
accessibility bus is absent.
