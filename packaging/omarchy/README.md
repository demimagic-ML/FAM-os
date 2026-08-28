# Omarchy distribution integration

`packaging/arch/PKGBUILD` is the canonical FAM system package for x86_64 and
experimental aarch64 builds. The focused Omarchy package-repository recipe is
x86_64-only, matching the supported Omarchy target. Neither recipe installs QML
into a user's configuration; the independent signed plugin lives at
`demimagic-ML/omarchy-fam-plugin` and is managed by `omarchy plugin`.

Before package-repository inclusion, `bootstrap.sh` verifies the pinned FAM
release fingerprint, signed checksum manifest, checksum and detached package
signature before importing the key into pacman and installing. The x86_64
artifact is the official Omarchy target. aarch64 CI is experimental and is not
required by or attached to Omarchy releases.

The `.omarchy/package.json` and update script are the focused source for an
eventual `omacom-io/omarchy-pkgs` contribution:

```bash
packaging/omarchy/sync-package-source.sh ../omarchy-pkgs
```

Current Omarchy does not discover third-party usage collectors from PATH and
does not recognize an arbitrary executable as a default agent. FAM therefore
ships a user timer that writes the tested `fam.json` compatibility record plus
standalone `fam`, `fam goal`, `fam console` and `omarchy-fam` launchers. The
default-agent change under `integrations/omarchy/upstream/` remains a separate
upstream proposal; it is not claimed as current native support.

Published package lifecycle hooks never edit a user's home. User setup is
explicit and unattended-capable:

```bash
fam-os setup omarchy --yes --enable-widget
```
