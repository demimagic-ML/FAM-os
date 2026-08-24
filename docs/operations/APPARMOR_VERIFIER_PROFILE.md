# Install and diagnose the FAM_OS verifier profile

## When this is required

Ubuntu hosts may keep AppArmor enabled and set
`kernel.apparmor_restrict_unprivileged_userns=1`. FAM_OS detects that policy and
requires the signed `fam-os-userns` profile for Bubblewrap verification.

FAM_OS does not disable the host restriction and does not reuse an unrelated
application profile.

## Install the signed profile

First install the signed FAM_OS release as the owning user. Then inspect and
load the exact profile from that release, replacing `/path/to/fam-prefix` with
the installation prefix:

```bash
sudo install -o root -g root -m 0644 \
  /path/to/fam-prefix/active/share/service_unit/fam-os-userns \
  /etc/apparmor.d/fam-os-userns
sudo apparmor_parser -r /etc/apparmor.d/fam-os-userns
```

The administrator action is intentionally separate from the user installer.
Do not run a mutable user-owned helper as root.

## Diagnose the installed boundary

```bash
/path/to/fam-prefix/bin/fam-os \
  --prefix /path/to/fam-prefix \
  host-security diagnose
```

A healthy receipt reports `healthy: true`, `status: completed`, and
`isolation: bubblewrap`. On an unrestricted host `apparmor_profile` is null. On
a restricted AppArmor host it must be `fam-os-userns`.

## Remove host policy separately

Only after every FAM_OS installation on the host is removed:

```bash
sudo apparmor_parser -R /etc/apparmor.d/fam-os-userns
sudo rm /etc/apparmor.d/fam-os-userns
```

The user-level total-removal command intentionally does not remove shared
system policy.

## Total user removal

The destructive command requires confirmation and exact roots:

```bash
/path/to/fam-prefix/bin/fam-os \
  --prefix /path/to/fam-prefix \
  remove \
  --state-root /path/to/fam-state \
  --runtime-root /run/user/UID/fam-os \
  --extension-root /home/USER/.vscode/extensions \
  --confirm
```

It stops both managed services and removes only signed or owner-marked FAM_OS
surfaces. It refuses unmarked or overlapping paths.

