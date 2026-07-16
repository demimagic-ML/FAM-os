# Cgroup-v2 adapter ownership

Implements read-only resource observation for a service located by another adapter. It owns safe cgroup path resolution and parsing of memory current, peak, ceiling, swap, events, and pressure files.

It does not select budgets, mutate cgroup files, start services, or decide scheduling and eviction policy. A missing service or unavailable controller degrades to no snapshot; malformed controller data raises a stable supervisor error.
