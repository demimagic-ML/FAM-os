# Read-Only Linux Application Discovery

## Purpose

Phase 5.5 discovers installed applications, safe launch metadata, current-user
process identities, X11 windows, and focused-window identity without granting
launch, observation, or action authority. It produces a provider-neutral
`ApplicationDiscoverySnapshot` for later Application Fabric adapters.

Discovery is not permission. Knowing that a process/window exists does not
authorize reading its document, title, controls, files, or memory.

## Installed applications and launch metadata

The adapter reads freedesktop `.desktop` files from explicitly composed XDG
application directories in precedence order. It accepts visible
`Type=Application` entries with a name and `Exec`, skips hidden/NoDisplay entries
by default, and records stable identity, display name, optional
`StartupWMClass`, direct executable/static arguments, file/URI placeholder
support, terminal requirement, and whether a known shell is involved.

`Exec` is parsed as data with no subprocess or shell. Dynamic field codes are
removed and recorded; unsupported embedded codes, malformed quoting, nulls, and
newlines reject. Shell-wrapped metadata remains discoverable but is marked
`safe_without_shell=False` and is not authorization to launch.

## Process discovery

The procfs adapter enumerates numeric `/proc` entries and reads only bounded
`status`, `stat`, and the `exe` link. It filters to the configured Unix UID and
does not read command-line arguments or environment variables, which frequently
contain paths, tokens, and secrets.

Process identity includes PID, parent PID, UID, executable basename, kernel
command name, and start-time ticks. PID plus start time lets later consumers
detect PID reuse. Races and inaccessible processes are skipped; unavailable
procfs and configured count limits produce explicit safe issues.

## Window and focus discovery

The first window provider implements X11 EWMH discovery through shell-free,
bounded `xprop` argument tuples. It reads client/active window IDs, PID, and
`WM_CLASS`. `_NET_WM_NAME` is read only when an explicit privacy option enables
titles. Titles are excluded by default because they often reveal document names,
URLs, messages, or other user content.

There is no universal Wayland API for enumerating every application's windows.
Non-X11 or unavailable sessions therefore report
`linux.window_discovery.unavailable` rather than pretending completeness or
using screen/control fallbacks. Desktop-specific semantic or accessibility
providers can be added behind the same snapshot later.

## Correlation

Processes are associated with desktop entries only when executable basename has
one unambiguous owner. Windows prefer the already-correlated process identity,
then use a unique case-insensitive `StartupWMClass` match. Ambiguous matches stay
unassigned rather than being presented as fact.

## Live reference evidence

On the reference Ubuntu GNOME X11 workstation, the privacy-default snapshot on
2026-07-16 found 51 visible launchable desktop entries, 291 current-user
processes, 18 X11 windows, one focused window correlated to an installed
application, zero discovery issues, and zero captured window titles. Counts are
live-state evidence, not compatibility constants.

## Security boundary

- Every probe is read-only and shell-free.
- No process is launched, focused, signaled, memory-inspected, or controlled.
- No command arguments, process environments, or window titles are captured by
  default.
- Discovery failures are explicit and do not silently fall back to screen/input.
- Launch execution remains a future permissioned action adapter.
