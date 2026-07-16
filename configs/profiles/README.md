# Hardware Validation Profiles

These checked strict-schema documents are reusable desired policy, not live machine snapshots.

- `compat-cpu-16gb.json` requests the minimum CPU-only service envelope: 16 GiB total service memory, 2 GiB reserved inside that envelope, 14 GiB scheduler memory, zero service swap, and no accelerator visibility or placement.
- `full-reference-workstation.json` exposes discovered CPU, RAM, accelerator, and cache-eligible storage tiers while reserving 2 logical CPUs, 12 GiB system RAM, 1 GiB per accelerator, and 100 GiB free storage.

The full profile deliberately contains no GPU ID, mount path, model name, physical RAM total, or captured availability. Those facts belong to a privacy-reviewed `DiscoveredResourceState` captured for each run.
