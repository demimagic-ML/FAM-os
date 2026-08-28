# Omarchy compatibility and migration policy

The machine-readable source of truth is
[`packaging/omarchy/support-matrix.json`](../../packaging/omarchy/support-matrix.json).

| Host | Architecture | Status |
|---|---:|---|
| Omarchy 4.x Quattro | x86_64 | Supported |
| Omarchy-compatible Arch/Hyprland | aarch64 | Experimental, not a release gate |
| Omarchy 3.x | any | Unsupported |
| Ordinary Arch + Hyprland | x86_64/aarch64 | FAM core supported without Omarchy shell |

FAM detects the Omarchy package/version, `OMARCHY_PATH`, shell IPC, Hyprland,
UWSM and Quickshell independently. Hyprland alone does not identify Omarchy.

## Version negotiation

Every widget status response contains `apiVersion`, `pluginMinVersion` and
`serviceVersion`. Plugin 0.1.1 accepts API version 1. An unknown major API or a
service-required plugin version newer than the checkout makes the plugin quiet
and unavailable; it does not stop the FAM service or an active goal.

If Omarchy 5 arrives before a qualified FAM release, setup refuses shell-plugin
installation. Core FAM and ordinary Arch/Hyprland operation remain available.
The same independent degradation applies to AT-SPI, screenshots, controlled
input, Codex, Ollama and browser testing.

## Upgrade and rollback

Pacman upgrades only system-owned files. User database/schema migrations run
inside FAM's versioned storage lifecycle and retain the previous release's
recovery evidence. Plugin updates use `omarchy plugin update fam.os --yes` and
must remain signed by the pinned FAM release key. A failed plugin update does
not modify goal state.

Normal package removal preserves configuration, goals, history, candidates and
recovery checkpoints. `fam-os purge --user-data --yes` is the only supported
destructive user-data path. Package downgrade/reinstall therefore remains
possible without silently discarding a long-running goal.

## Upstream extension boundaries

The FAM usage timer writes
`$XDG_STATE_HOME/omarchy/agents/usage/fam.json`. This is a tested compatibility
record for Omarchy's current internal usage schema, not a formal third-party
collector extension point. It is contract-tested for every supported Omarchy
release.

`fam`, `fam tui`, `fam chat`, `fam goal`, `fam console` and `omarchy-fam` are
supported FAM launchers. The FAM package implements explicit interactive and
prompt contracts. Native `omarchy default agent fam`, scratchpad and
`omarchy agent prompt` routing become available when the separate upstream
Omarchy contribution is accepted; the package does not claim that upstream
merge before it happens.
