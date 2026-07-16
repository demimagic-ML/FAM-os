# Linux installation lifecycle

The `fam-os` command provides `install`, `update`, `diagnose`, `repair`, and
`remove` against an explicit owner-private prefix. Installation copies an
immutable Python package release, atomically switches `current`, creates a Shell
launcher and hardened systemd user unit, and records their digests. Diagnosis
checks privacy, release-pointer containment, and every managed digest. Repair
creates a new immutable release. Removal requires the private FAM_OS marker and
refuses dangerous shallow paths.

The generated release contains executable `fam-service` and `fam-shell`
launchers bound to the Python interpreter that performed installation. Its
systemd user unit has been checked with `systemd-analyze --user verify` and
starts `fam-service`; it no longer targets a missing module.

Example:

```bash
fam-os --prefix "$HOME/.local/share/fam-os" install \
  --source-package ./src/fam_os --release-id 0.1.0
fam-os --prefix "$HOME/.local/share/fam-os" diagnose
systemctl --user link "$HOME/.local/share/fam-os/systemd/fam-os.service"
systemctl --user daemon-reload
systemctl --user enable --now fam-os.service
```

Use `systemctl --user status fam-os.service` to check startup. Before removal:

```bash
systemctl --user disable --now fam-os.service
fam-os --prefix "$HOME/.local/share/fam-os" remove
systemctl --user daemon-reload
```
