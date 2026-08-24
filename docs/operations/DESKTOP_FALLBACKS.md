# Desktop fallback operation

Accessibility and screen/input are last-resort Application Fabric mechanisms.
They are disabled when this file is absent:

```text
$XDG_DATA_HOME/fam-os/config/fallbacks.json
```

The file must be owned by the FAM_OS service user and mode `0600`. Restart the
service after changing it. Enabling either mechanism without
`privacy_acknowledged: true` is rejected.

## Exact-target example

```json
{
  "contract_version": "fam.product.fallbacks/v1alpha1",
  "accessibility": {
    "enabled": true,
    "privacy_acknowledged": true,
    "include_text": false,
    "actions_enabled": true,
    "allowed_actions": ["click", "press", "activate"],
    "targets": [
      {
        "connector_id": "atspi.editor",
        "instance_id": "atspi-editor",
        "process_id": 12345
      }
    ]
  },
  "screen_input": {
    "enabled": true,
    "privacy_acknowledged": true,
    "actions_enabled": false,
    "allowed_kinds": ["pointer_click"],
    "allowed_keys": ["Control_L", "Shift_L", "Escape"],
    "targets": [
      {
        "connector_id": "screen.editor",
        "instance_id": "screen-editor",
        "application_id": "org.example.Editor",
        "process_id": 12345,
        "window_id": "0x04a00007"
      }
    ]
  }
}
```

Targets are never auto-discovered into authority. Process and X11 window IDs
must match the running application exactly. A changed process or window needs a
new owner-approved configuration. Connector and instance IDs must be unique
across both mechanisms.

## Authority and privacy

- `enabled` activates bounded observation for only the listed targets.
- `include_text` affects accessibility observations only. Password/protected
  controls remain redacted by the bridge.
- `actions_enabled` is independent of observation. When false, no action
  capability is registered.
- Accessibility actions are restricted to `allowed_actions` and revalidate the
  exact object fingerprint immediately before invocation.
- Screen actions are restricted to `allowed_kinds` and `allowed_keys`, require
  the exact focused X11 window, and revalidate the captured scene before input.
- Every fallback action is irreversible in the capability contract and always
  requires confirmation.
- Core independently re-observes the accessibility poststate or screen frame.
  Adapter claims alone cannot produce a verified result.
- Screen capture/input degrades unavailable outside a compatible X11 session;
  it does not bypass Wayland security controls.

## Console visibility

Open **Applications** in FAM Console. It shows whether each mechanism is
disabled, observation-only, degraded, or action-capable, together with its
approved scopes, privacy impact, action primitives, and confirmation policy.
The authenticated API representation is `GET /api/v1/integrations`.

Removing the file and restarting the service unregisters every fallback
capability. Configuration changes never grant persistent permission by
themselves; normal Core permission and approval checks still apply.
