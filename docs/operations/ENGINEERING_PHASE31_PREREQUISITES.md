# Phase 31 Engineering Qualification Prerequisites

## Dedicated verifier AppArmor profile

Ubuntu's restricted unprivileged-userns policy requires the signed verifier
worker profile. An owner administrator must inspect and load it interactively:

```bash
sudo install -o root -g root -m 0644 packaging/systemd/fam-os-userns /etc/apparmor.d/fam-os-userns
sudo apparmor_parser -r /etc/apparmor.d/fam-os-userns
sudo apparmor_status | grep fam-os-userns
```

Loading this profile is a host security-policy mutation. Core and models must
not bypass the password prompt or infer permission from ordinary engineering
authority. After loading it, rerun the signed hardware matrix and preserve both
the prior failing evidence and the new result.

## Independent review

Use `docs/security/ENGINEERING_SECURITY_REVIEW_TEMPLATE.md`. The implementing
agent cannot satisfy independence.

## Soak clock

The 24-hour clock starts only after the AppArmor prerequisite, signed installed
matrix, and pre-soak security suite pass. Any verifier-boundary failure restarts
the clock. A development-duration run is diagnostic only and cannot create a
passing `EngineeringPressureSoakReport`.
