# Omarchy 4 integration architecture

The Omarchy adapter is one presentation/lifecycle edge around the same FAM
core, Goal Mode and application harness used elsewhere on Linux.

```text
Omarchy 4 x86_64
  -> independent signed fam.os Git plugin
       -> HTTP GET /api/v1/status
       -> WebSocket /api/v1/events
       -> idempotent HTTP POST named controls
  -> unprivileged fam-os.service
       -> durable Goal Mode and candidate workspace
       -> Codex or local-model engineering provider
       -> browser/native application-test harness
  -> fam-os-desktop.service -> UWSM + Hyprland session bridge
  -> fam-os-usage.timer -> internal-compatible fam.json record
  -> Omarchy snapshots -> system-changing goals only
```

## Ownership and locations

Pacman owns executables, Python modules, user-unit definitions, desktop files,
icons, documentation and the pinned public signing key. It never selects a
desktop user or writes into a home directory.

The user setup command owns only explicit XDG locations:

- configuration: `$XDG_CONFIG_HOME/fam-os/`;
- durable state/candidates: `$XDG_DATA_HOME/fam-os/`;
- operational state: `$XDG_STATE_HOME/fam-os/`;
- cache: `$XDG_CACHE_HOME/fam-os/`;
- per-start token/socket descriptors: `$XDG_RUNTIME_DIR/fam-os/`;
- Omarchy plugin checkout: `$XDG_CONFIG_HOME/omarchy/plugins/fam.os/`;
- usage compatibility record: `$XDG_STATE_HOME/omarchy/agents/usage/fam.json`.

The plugin checkout is a normal Omarchy-managed Git repository and receives no
runtime writes. Disable/reload/update only destroys QML presentation state;
goals continue in the persistent service.

## Transport boundary

`ConsoleHttpServer` refuses non-loopback binds. Widget requests additionally
require the per-start owner-private token, a loopback Host and an absent or
explicitly accepted Origin. WebSocket authentication uses the same token in
the upgrade URI because QML cannot attach the private header. Tokens rotate at
service start and never enter durable state.

POST bodies are bounded and require a unique `commandId`. The service caches a
bounded set of command receipts so shell retries cannot repeat a confirmed
effect. Each first execution appends a content-free audit event under FAM state.
The widget API exposes status, pause, resume, cancel, guidance, Console open,
candidate open and agent submission; it has no arbitrary command route.

## Agent and application ecosystem

Capability discovery records Codex, Claude Code, OpenCode, Copilot, Ori,
Ollama/LM Studio-compatible endpoints, browsers, AT-SPI, Hyprland capture and
controlled input. Routing belongs to FAM. Omarchy's current default-agent and
usage collector registries are not general third-party plugin APIs, so the
standalone launchers and compatibility timer remain explicit boundaries until
their focused upstream contributions are accepted.

Application tests prefer semantics over pixels: Playwright, application/MCP
capabilities and AT-SPI come before Hyprland capture and controlled input. The
selected workspace/grant is the allowlist; candidate paths and runtime paths
reject symlink traversal. The service runs as the desktop user with
`NoNewPrivileges=true`, never as root, and installs no sudo policy or privileged
helper.

## Distribution and migration

Version tags produce a deterministic source archive and official x86_64 Arch
package. The experimental aarch64 build is informational and cannot block or
enter an Omarchy release. Release checksums and packages receive detached
signatures from the pinned FAM key in addition to GitHub build provenance.

The package and `omarchy-fam-plugin` repositories have independent signed
provenance. `fam-os setup omarchy` verifies plugin origin and signed HEAD before
accepting it. Unsupported future Omarchy/plugin API majors disable only shell
integration; the core service and durable goals remain available.

See [compatibility and migrations](../compatibility/omarchy.md) and the
[installation guide](../installation/omarchy.md).
