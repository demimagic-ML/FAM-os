# Handoff 0171: Console workspace context and secure launch

**Date:** 2026-07-18  
**Plan step:** Phase 23.6  
**Status:** Complete  
**Previous handoff:** `0170-action-intent-firewall-and-verified-directory-receipts.md`

## Objective

Make each live VS Code workspace a distinct selectable Console task context and
provide an owner-safe way to open a freshly authenticated Console session.

## Scope completed

- Split application contexts by application instance and registered resource
  scope instead of collapsing all VS Code workspaces into one application row.
- Filter scoped capabilities to the selected workspace while retaining truly
  unscoped capabilities.
- Carry the selected workspace URI into the task's bounded context unless the
  user supplies a more specific resource.
- Exclude unavailable application instances from task choices.
- Added a `fam-os console` launcher that proves loopback availability, validates
  the private bootstrap-token file, places the token only in the URL fragment,
  opens the browser through bounded `xdg-open`, and emits a token-free receipt.
- Used the launcher after a clean service restart and proved authenticated
  session exchange and snapshot retrieval both returned HTTP 200.

## Explicitly not completed

- Persistent whole-workspace indexing is not inferred from selection; it still
  requires the explicit expiring grant defined by ADR 0126.
- A fresh signed release bundle was not built for this source correction.

## Architecture and decisions

The Console remains an unprivileged Core client. Workspace identity is derived
from connector registration and its permitted resource scopes, not from browser
filesystem access. Context IDs use a stable digest rather than disclosing the
URI in an identifier. An explicit resource remains narrower and therefore wins
over the selected workspace default.

The bootstrap token is exchanged once for an HttpOnly session cookie. The
launcher does not print, persist, or put the token in the HTTP request target;
the browser reads it from the fragment and immediately removes that fragment.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/console/application_contexts.py` | Workspace-aware context projection. |
| `src/fam_os/console/tasks.py` | Delegate context construction to the projection. |
| `src/fam_os/console/static/app.js` | Bind selected workspace resource to task context. |
| `src/fam_os/product/console_launch.py` | Token-safe Console launch use case. |
| `src/fam_os/adapters/linux/console_browser.py` | Loopback probe and bounded browser adapter. |
| `src/fam_os/product/console_cli.py` | Token-free launcher receipt. |
| `src/fam_os/product/cli.py` | Public `console` command. |
| `tests/integration/test_console_http.py` | Multi-workspace and static UI regressions. |
| `tests/unit/test_console_launch.py` | Token file and launch security tests. |
| `tests/unit/test_product_cli.py` | Signed-install command composition tests. |

## Public interfaces

- `fam-os --prefix PREFIX console [--runtime-root PATH] [--port PORT]`
- Console context documents may include `application_id` and
  `workspace_resource_ref`.

## Validation

```bash
.verification-venv/bin/python -m unittest tests.integration.test_console_http
.verification-venv/bin/python -m unittest tests.unit.test_console_launch tests.unit.test_product_cli
systemctl --user restart fam-os-current.service
.verification-venv/bin/python -m fam_os.product.cli --prefix /home/demimagic/.local/share/fam-os-current console --runtime-root /run/user/1000/fam-os-current --port 8765
```

Result: 17 focused tests passed. The restarted service was active on
`127.0.0.1:8765`; bootstrap exchange and authenticated snapshot both returned
HTTP 200, and the launcher opened a new browser tab without printing the token.

## Evidence and artifacts

- `tests/integration/test_console_http.py`
- `tests/unit/test_console_launch.py`
- `tests/unit/test_product_cli.py`

## Known limitations and risks

- Browser process launch necessarily transfers the fragment URI to `xdg-open`;
  it is absent from HTTP logs and FAM receipts but transiently exists in local
  process arguments.
- Browser-local task history is still session-scoped.

## Operational notes

Use the launcher rather than reusing an expired tab. A bare
`http://127.0.0.1:8765` page can load static assets but cannot create an
authenticated API session without a fresh bootstrap exchange.

## Recommended next entry point

Continue the Phase 23 audit at production resource admission. Read
`src/fam_os/product/composition/live_capacity.py` and compare it with Phases 7
and 11 before claiming installed resource-awareness.
