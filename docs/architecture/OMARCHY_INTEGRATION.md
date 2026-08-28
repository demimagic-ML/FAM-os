# Omarchy 4 integration architecture

The Omarchy adapter is one presentation/lifecycle edge around the same FAM
core, Goal Mode and application harness used elsewhere on Linux.

```text
Omarchy 4 x86_64
  -> independent signed fam.os Git plugin
       -> native BarWidget + attached Panel/KeyboardPanel
       -> HTTP GET /api/v1/status
       -> WebSocket /api/v1/events
       -> idempotent HTTP POST named controls
  -> omarchy-fam interactive/prompt launcher
       -> current-directory + demand-shaped session context
       -> FAM agent supervisor -> Codex or local engineering provider
  -> user menu extension -> Console, Goal, Doctor, Repair
  -> post-update hook -> diagnose and notify only
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
- Omarchy menu extension: `$XDG_CONFIG_HOME/omarchy/extensions/omarchy-menu.jsonc`;
- Omarchy update hook: `$XDG_CONFIG_HOME/omarchy/hooks/post-update.d/fam-os`;
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
controlled input. FAM is the supervisory agent boundary: it chooses an
engineering provider while retaining the objective, plan, evidence, candidate,
recovery and verification lifecycle. The terminal, widget and Console are
different presentations of that same durable service state.

The Omarchy launcher always supplies the current directory and a bounded source
identifier. FAM adds active-window/Hyprland observations only for desktop or
application tasks and listener/project-command observations only for run,
server, browser or test tasks. The observed context is persisted separately,
bounded before model use and explicitly labelled as non-authoritative data.

Omarchy's default-agent registry requires a focused upstream change. The
checked-in contribution maps FAM scratchpad/default launches to an interactive
terminal, prompt launches to a normal FAM request and crash diagnosis to a
source-labelled prompt. The usage collector remains a tested compatibility
record rather than a general third-party extension API.

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

System-changing Goal Mode runs inspect configured Snapper roots before calling
Omarchy's snapshot command and persist the new `<config>:<snapshot-id>` values
plus the `omarchy snapshot restore` recovery command. Coding and ordinary
workspace goals never request a system snapshot. A successful command without
new Snapper IDs is treated as failure, not as recoverable evidence.

See [compatibility and migrations](../compatibility/omarchy.md) and the
[installation guide](../installation/omarchy.md).
