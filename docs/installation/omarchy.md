# Install FAM on Omarchy 4

FAM officially supports Omarchy 4.x Quattro on x86_64. Omarchy 3 is
unsupported. aarch64 remains an experimental Arch/Hyprland path and is not an
official Omarchy release gate. See the [support matrix](../compatibility/omarchy.md).

## Signed bootstrap before package-repository inclusion

Inspect the installer first:

```bash
curl -fsSL https://raw.githubusercontent.com/demimagic-ML/FAM-os/main/packaging/omarchy/bootstrap.sh | less
```

Then run those same reviewed bytes:

```bash
curl -fsSL https://raw.githubusercontent.com/demimagic-ML/FAM-os/main/packaging/omarchy/bootstrap.sh | bash
```

Do not advertise `install.fam-os.dev` until its DNS, HTTPS and deployed bytes
are owned and verified. The checked-in bootstrap:

1. refuses root execution and confirms Omarchy 4.x and architecture;
2. requires 6 GiB available disk space;
3. downloads the x86_64 package, detached signature, checksum manifest,
   manifest signature and public key from one stable release;
4. matches the key against pinned fingerprint
   `EFBCEDEEC8C1C058C5AA64F97D8D854748E4D62A`;
5. verifies the signed checksums and package signature independently;
6. imports that pinned key into pacman's trust database and installs with
   `pacman -U`;
7. runs `fam-os setup omarchy --yes --enable-widget` and the doctor;
8. prints ordinary removal and explicit destructive-purge commands.

The package uses Arch system dependencies and never runs `pip install` during
setup, service startup or upgrade.

## Package-repository installation

After the focused FAM recipe is accepted by Omarchy's package repository:

```bash
sudo pacman -S fam-os
fam-os setup omarchy --yes --enable-widget
```

Pacman runs only system-owned lifecycle hooks; it never edits a desktop user's
home. Setup must run as the actual desktop user.

## What user setup does

Setup is idempotent. It detects the host and agent/model ecosystem, installs
the independent signed Git plugin through Omarchy, enables the unprivileged
user services, writes the FAM usage compatibility record, runs diagnostics and
opens the authenticated Console. The public plugin repository is:

```text
https://github.com/demimagic-ML/omarchy-fam-plugin.git
```

Omarchy clones it to `$XDG_CONFIG_HOME/omarchy/plugins/fam.os`. FAM verifies
that the origin matches and that `HEAD` is signed by the pinned FAM release key.
The package does not copy QML into that directory. The plugin directory remains
read-only at runtime.

Useful lifecycle commands:

```bash
fam-os doctor --omarchy
fam-os doctor --omarchy --json
fam-os repair omarchy --service
fam-os repair omarchy --widget --yes
fam-os remove omarchy-integration
```

Plugins execute unsandboxed inside the Omarchy shell, which is why widget
installation requires an interactive confirmation or explicit `--yes`.

## Launch and work

```bash
fam
fam console
fam "Explain this project and run its focused tests"
fam goal "Finish this application, test its behavior, and verify the build"
omarchy-fam --goal "Finish this application and verify it"
```

These are supported standalone launchers. Native `omarchy default agent fam`
and `omarchy agent prompt` support remain a separate upstream contribution and
are not claimed by this release.

## Widget transport and failure behavior

The `fam.os` bar widget summons its panel with:

```bash
omarchy-shell shell summon fam.os '{}'
```

The service binds only to `127.0.0.1`. A token is generated at every service
start under `$XDG_RUNTIME_DIR/fam-os/` with mode `0600`. The plugin uses HTTP
GET for initial/fallback state, WebSocket for live events, and idempotent HTTP
POST commands. Browser origins are rejected, request bodies are bounded, and
the API exposes only named controls—never arbitrary shell execution.

The fallback interval is 30 seconds. WebSocket reconnects back off from one to
30 seconds; messages are bounded to 64 KiB; malformed events are ignored and
repaired by the next GET. Service unavailability is quiet. Plugin disable,
update, shell restart, logout and reload do not stop or erase an active goal.
Shell restart is a recovery action, not part of routine installation.

## Application testing

FAM uses Playwright plus structured DOM/accessibility state for web apps,
native/MCP application capabilities when available, AT-SPI for accessible
Linux apps, and Hyprland identity/capture with controlled input only as a
fallback. The application-test lifecycle owns launched processes, waits for
readiness, retains console/network/trace/screenshot evidence, checks declared
behavior and stops only resources it created.

See [Omarchy application testing](../operations/OMARCHY_APPLICATION_TESTING.md).
Screen-capture, input-control, workspace, widget and package trust boundaries
are documented in [Omarchy plugin and agent security](../security/OMARCHY_PLUGIN_AND_AGENT_BOUNDARY.md).

## Update, remove and purge

```bash
sudo pacman -Syu
systemctl --user daemon-reload
fam-os repair omarchy --service
```

Ordinary removal preserves user state:

```bash
fam-os remove omarchy-integration
sudo pacman -Rns fam-os
```

To erase all FAM user data deliberately, do it while FAM is still installed:

```bash
fam-os purge --user-data --yes
```

The purge refuses symlinked, unowned or ambiguous targets and affects only the
explicit FAM XDG directories plus the `fam.json` compatibility record.

## Release qualification

Unit/contract tests, a clean Arch container package install and real browser
application E2E run in CI. The destructive Omarchy gate runs on a disposable
x86_64 Omarchy 4 VM and checks install, signed plugin lifecycle, services,
WebSocket API, active-goal persistence, shell reload, reboot, upgrade, removal
and reinstall:

```bash
FAM_OS_DISPOSABLE_VM=1 tools/omarchy/vm-e2e.sh \
  --target user@disposable-omarchy-vm \
  --package dist/fam-os.pkg.tar.zst \
  --reboot --verify-paused-goal --remove-reinstall
```

The disposable VM must have a working FAM inference provider. The gate creates
its own real goal, pauses it, reboots, and verifies the same durable goal and
candidate rather than relying on pre-seeded database state.
