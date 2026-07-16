# Handoff 0045: Linux accessibility bridge

**Date:** 2026-07-16  
**Plan step:** Phase 5.7  
**Status:** Complete  
**Previous handoff:** `0044-deterministic-linux-capabilities.md`

## Objective

Implement a bounded Linux AT-SPI observation and action bridge for unmodified
applications without exposing GI objects, protected content, arbitrary action
indexes, or stale object references to Core or models.

## Scope completed

- Provider-neutral accessibility node, snapshot, reference, proposal, and raw
  evidence contracts.
- Dynamic GI-backed AT-SPI provider with explicit unavailable behavior.
- Breadth-first node/depth/text/action bounds with bounded queue growth.
- Text that is neither read nor exposed unless explicitly requested.
- Password-role name, description, text, and action redaction at two boundaries.
- Exact named action allowlist and action-count bound.
- Full SHA-256 object identity fingerprint plus child-path re-resolution before
  prepare and again immediately before perform.
- Process-scoped accessibility connector declarations with irreversible,
  always-confirmed action policy and a required poststate condition.
- Fake-driven failure/security tests, architecture guards, and live read-only
  session validation.

## Explicitly not completed

- Screen capture, OCR, keyboard injection, or pointer input (Phase 5.10).
- Application-specific semantic state or native editor commands (Phase 5.9).
- Core composition of confirmation, postconditions, audit, and undo metadata
  (Phase 5.11).
- Live action invocation; tests intentionally make no desktop mutation.

## Architecture and decisions

ADR 0045 keeps AT-SPI behind `AccessibilityProvider`; GI objects never enter
Application Fabric contracts. Observations are structurally and content bounded.
Password nodes are content-free. Actions are selected by approved names rather
than arbitrary indexes and are re-resolved from a process root and index path,
then fingerprint-checked at both stages. Provider invocation is only raw evidence,
not verified task success.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/applications/accessibility.py` | Provider-neutral public values. |
| `src/fam_os/adapters/linux/accessibility/ports.py` | Provider boundary. |
| `src/fam_os/adapters/linux/accessibility/types.py` | Adapter-owned normalized values. |
| `src/fam_os/adapters/linux/accessibility/atspi.py` | Defensive GI provider. |
| `src/fam_os/adapters/linux/accessibility/bridge.py` | Bounded observation and stale-safe actions. |
| `src/fam_os/adapters/linux/accessibility/catalog.py` | Process-scoped capability declarations. |
| `tests/unit/test_linux_accessibility_bridge.py` | Bounds, redaction, action, stale, catalog tests. |
| `tests/integration/test_linux_accessibility_live.py` | Mutation-free current-session probe. |
| `tests/architecture/test_linux_accessibility_boundary.py` | Dependency and process-spawn guards. |
| `docs/protocols/LINUX_ACCESSIBILITY_BRIDGE.md` | Contract, privacy, and limitation guide. |
| `docs/decisions/0045-bounded-atspi-accessibility-bridge.md` | Durable boundary decision. |

## Public interfaces

- `AccessibleObjectRef`, `AccessibleAction`, `AccessibleNode`, and
  `AccessibilitySnapshot`.
- `AccessibilityActionProposal` and `AccessibilityActionEvidence`.
- `AccessibilityProvider`, `ProviderAccessibleNode`, and
  `ProviderAccessibleAction`.
- `AccessibilityBridgePolicy`, `LinuxAccessibilityBridge`, and
  `GiAtspiProvider`.
- Accessibility observation/action descriptors and registration builder.

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest tests.integration.test_linux_accessibility_live tests.unit.test_linux_accessibility_bridge tests.architecture.test_linux_accessibility_boundary
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
python3 <AST module/function size gate>
larry index . && larry health .
```

Result: all 13 focused tests passed under system Python; the MCP environment
passed all 490 tests with one live
AT-SPI skip because GI is not installed there; system Python passed all 490
tests with two expected environment-dependent skips. All 35 schemas matched,
compile succeeded, and 240 implementation modules had no module over 300 lines
or function over 50 lines. Larry indexed 648 files / 1,942 symbols with 8,573
nodes / 31,410 edges and clean health. The persisted code graph was refreshed
as `fam-os-code-graph` with 9,537 nodes / 34,400 edges.

The live system-Python probe reported AT-SPI available, 28 top-level/readable
application roots, and an unambiguous GNOME Shell snapshot of exactly 64 bounded
nodes with `truncated=True`, zero text nodes, zero protected nodes in that sample,
and zero exposed allowlisted actions. No action was invoked.

## Evidence and artifacts

- `docs/protocols/LINUX_ACCESSIBILITY_BRIDGE.md`
- `docs/decisions/0045-bounded-atspi-accessibility-bridge.md`
- `tests/integration/test_linux_accessibility_live.py`

## Known limitations and risks

- Applications control their own accessibility claims; roles and actions remain
  untrusted evidence.
- Index paths and fingerprints intentionally fail closed when dynamic UI changes.
- Same-session AT-SPI is not a hardened isolation boundary.
- Invocation evidence does not establish the intended application poststate.

## Operational notes

System Python has GI/AT-SPI and the user accessibility bus was live. The isolated
MCP test venv lacks GI, so the live test degraded through an explicit skip. No
package, service, application, window, or accessibility action was changed.

## Recommended next entry point

Begin Phase 5.8. Read Core ingress/lifecycle public contracts and the Application
Fabric registry/permission contracts, then define a small Shell client port and
presentation state before implementing a terminal UI. The Shell must remain an
unprivileged client and must not duplicate Core admission, model, permission, or
verification policy.
