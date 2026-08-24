# Operating-state adaptation

Phase 11.4 deterministically combines battery, charging, thermal, foreground-load, and idle observations. Low unplugged battery caps experts at economical and disables speculation. Thermal protection caps at micro. High foreground load disables prefetch. Background adaptation is enabled only after five idle minutes with no protective reason.

Every restriction has a reason code and user preferences cannot override it.

## Installed production projection

The installed product observes the policy at the same boundary used for local
model selection and predictive prewarming. The Linux adapter reads system
battery state, the hottest valid sysfs or NVIDIA temperature, normalized
one-minute host load, and GNOME session idle time through bounded shell-free
probes. Peripheral batteries with `scope=Device` do not stand in for the host
battery.

Selection receives raw available RAM and VRAM together with the selected
validation-profile reserves. The full workstation retains 12 GiB host RAM and
1 GiB VRAM; the compatibility profile retains 2 GiB host RAM and exposes no
artificial GPU capacity. A managed Ollama cgroup further clamps new host
allocation to `memory.max - memory.current`. If that managed snapshot is
unavailable, new cold host allocation is denied; already resident experts do
not pretend to require a second allocation.

Protective tier caps apply even to a resident or explicitly escalated model.
Unknown thermal state disables speculation, and predictive model prewarming
requires both prefetch authority and five-minute idle background authority.
Ordinary user-requested inference may still use a permitted tier when a
nonessential background observation is unavailable. External Ollama remains an
explicitly unmanaged compatibility mode and is labelled
`cgroup.external_runtime`; it does not receive a fabricated cgroup ceiling.

This projection does not give predictive adaptation eviction authority.
Confirmed unload, active leases, and durable residency remain Scheduler-owned
and must be composed separately before production can claim neural-pager
eviction.
