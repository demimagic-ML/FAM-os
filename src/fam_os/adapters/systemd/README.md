# User-systemd adapter ownership

Implements the provider-neutral service lifecycle port with `systemd-run --user` and `systemctl --user` through an injected, bounded, shell-free command runner.

It owns unit-name normalization, transient-unit property mapping, and systemd status parsing. It does not decide which service to launch, whether resources are sufficient, when a model should be evicted, or whether an application is ready.

The lifecycle accepts a provider-neutral service-definition projector and an optional explicit AppArmor profile. This lets an access adapter wrap the registered base command at launch while the systemd adapter continues to own service and cgroup mechanics. The profile option is for a locally installed named policy; the adapter never changes host AppArmor configuration.

For Phase 3.6 the adapter also implements the provider-neutral failed-state reset
with `systemctl --user reset-failed`. The default remains `--collect`; an explicit
`retain_failed_state` setting uses `CollectMode=inactive` so failure evidence is
retained until recovery and the transient unit is collected after becoming
inactive.
