# FAM for Omarchy 4

This is the independent Git-backed `fam.os` plugin for Omarchy 4 Quattro. Its
entry point is an Omarchy `BarWidget`; it loads an attached native
`Panel`/`KeyboardPanel` using the shared `qs.Ui` components rather than a
standalone overlay. It shows durable goal progress in the bar and opens a
minimal control panel with:

- phase, elapsed time, plan and verification progress;
- current model, RAM/VRAM and last activity;
- recovery state and next retry;
- pause, resume, cancel, guidance, Console and candidate controls.

Install FAM first, inspect this repository, then let the supported lifecycle
install and enable the plugin through Omarchy:

```bash
fam-os setup omarchy --yes --enable-widget
```

Or use the official plugin command directly:

```bash
omarchy plugin add https://github.com/demimagic-ML/omarchy-fam-plugin.git \
  --enable --yes
```

The plugin is unsandboxed inside the Omarchy shell. It does not expose shell
execution and does not read FAM databases. It talks only to an authenticated
service bound to `127.0.0.1`: HTTP GET for initial/fallback state, WebSocket
for events, and idempotent HTTP POST for named controls. The token is rotated
at each FAM service start and stored with mode `0600` under
`$XDG_RUNTIME_DIR/fam-os/`.

The checkout is read-only at runtime. State, cache, configuration and runtime
files remain in their standard XDG FAM directories. Disabling, updating or
reloading the plugin never stops an active goal.

Omarchy 4.x on x86_64 is supported. Omarchy 3 is unsupported. aarch64 is an
experimental Arch/Hyprland path rather than an official Omarchy release gate.
