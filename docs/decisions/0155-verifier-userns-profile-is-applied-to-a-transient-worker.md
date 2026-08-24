# ADR 0155: Verifier userns profile is applied to a transient worker

Status: Accepted

## Context

The first 24-hour Phase 23.5 candidate failed on its first verifier-crash
recovery. The same Bubblewrap verifier passed from the development terminal but
failed from the installed user service. Ubuntu's restricted unprivileged-userns
policy transitions a truly unconfined service into `unprivileged_userns`, where
Bubblewrap cannot configure loopback or its namespaces.

The installed service also sets `NoNewPrivileges=true`. That is intentional,
but it makes both an in-process `aa-exec` transition and a systemd
`AppArmorProfile=` transition fail. Applying an unconfined userns profile to the
whole FAM daemon would broaden authority unnecessarily.

## Decision

FAM_OS signs and ships the dedicated `fam-os-userns` AppArmor profile. On hosts
where AppArmor's unprivileged-userns restriction is active, verifier execution
uses a short-lived transient user service created by the user systemd manager.

- The main `fam-os.service` retains `NoNewPrivileges=true`.
- Only the transient verifier service receives
  `AppArmorProfile=fam-os-userns`.
- That service immediately enters the existing Bubblewrap sandbox, which
  unshares network and all other namespaces, drops every capability, exposes
  only the declared read-only runtime, and applies process/RAM/no-swap limits.
- The manager-launched service uses `--pipe --wait --collect`, so verifier
  output and exit status remain bound to the requesting process and no unit is
  retained.
- The same injected sandbox instance is used by ordinary declared verification
  and Factory canary verification.
- `fam-os host-security diagnose` executes a sentinel in the installed
  Bubblewrap boundary and fails when the named profile cannot be applied.

Loading a system AppArmor profile remains an explicit administrator action.
The user-scoped installer never disables the host restriction or silently runs
a privileged helper.

## Consequences

- Installed verification works from a locked-down daemon on restrictive Ubuntu
  hosts without granting the entire daemon userns authority.
- A missing or unloadable profile produces `SandboxStatus.UNAVAILABLE`; it is
  never classified as a candidate failure or accepted result.
- Signed release health now requires the profile asset.
- Final installed qualification cannot pass until the administrator loads the
  dedicated profile. A development profile is not acceptable evidence.

## Alternatives considered

- Disable `kernel.apparmor_restrict_unprivileged_userns`: rejected because it
  weakens every process on the host.
- Reuse the `vscode` profile: rejected because it is unrelated, host-specific,
  and grants the wrong identity.
- Apply the FAM profile to the complete daemon: rejected because the verifier is
  the only component that needs the transition.
- Use `aa-exec` from the daemon: rejected because `NoNewPrivileges` correctly
  prevents that privilege transition.
- Remove `NoNewPrivileges` from the daemon: rejected because it weakens a
  broader and longer-lived boundary.

## Evidence

- `packaging/systemd/fam-os-userns`
- `src/fam_os/adapters/bubblewrap/commands.py`
- `src/fam_os/adapters/bubblewrap/runner.py`
- `src/fam_os/product/host_security.py`
- `src/fam_os/product/composition/verifier_unit.py`
- `src/fam_os/product/composition/factory_release.py`
- `tests/unit/test_bubblewrap_commands.py`
- `tests/unit/test_bubblewrap_runner.py`
- `tests/unit/test_host_security.py`

