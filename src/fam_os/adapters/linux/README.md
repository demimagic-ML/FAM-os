# Linux adapter ownership

This package implements the scheduler's read-only hardware discovery port using Linux procfs, device paths, standard-library platform and storage calls, and bounded version/probe commands.

It does not serialize profiles, choose scheduling policy, change system configuration, start services, or grant device access. Cgroup and systemd adapters are separate Phase 1.7 work.

Application discovery reads visible desktop entries, privacy-bounded current-user
procfs identities, and X11 EWMH window/focus identity. It never launches or
controls applications and excludes window titles by default. Non-X11 window
discovery degrades explicitly. See
`docs/protocols/LINUX_APPLICATION_DISCOVERY.md` and ADR 0043.

Deterministic capabilities provide scoped files, MIME, allowlisted primitive
D-Bus, portal OpenURI, and explicitly mapped tools over one bounded shell-free
runner. Raw success is not verified action success. See
`docs/protocols/DETERMINISTIC_LINUX_CAPABILITIES.md` and ADR 0044.

The level-3 accessibility bridge and level-4 screen/input fallback are isolated
subpackages. The latter captures only an exact focused X11 window and exposes
only one click or an allowlisted key chord behind exact-scene revalidation. See
`docs/protocols/RESTRICTED_SCREEN_INPUT_FALLBACK.md` and ADR 0048.

Live scheduler adapters map bounded NVIDIA readings to `gpu-N` and account only
configured absolute FAM cache directories with an entry limit and no symbolic
link traversal. They observe current state but do not grant placement authority.
See `docs/protocols/LIVE_SCHEDULER_RESOURCE_OBSERVATION.md` and ADR 0058.
