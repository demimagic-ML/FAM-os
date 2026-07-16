# Screen/input adapter ownership

This package owns the restricted Linux level-4 Application Fabric adapter.
`ScreenInputBridge` applies bounds, allowlists, exact-scene checks, and evidence.
Provider-specific X11 metadata, optional Pillow capture, and XTest injection stay
behind ports in this package.

The package does not choose permissions, approve actions, infer intent, run
models, declare task success, persist screenshots, or expose general desktop
control. The current provider targets only an exact active X11 window. See
`docs/protocols/RESTRICTED_SCREEN_INPUT_FALLBACK.md` and ADR 0048.
