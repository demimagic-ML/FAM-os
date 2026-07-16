# Handoff 0077: Sandbox process-limit correction

**Date:** 2026-07-16  
**Corrects:** Handoffs 0070 and 0071  
**Status:** Complete

The original Phase 8.2 `RLIMIT_NPROC=16` was incorrect because Linux accounts
that limit across the real user. On this desktop it prevented Bubblewrap from
creating namespaces and produced a false host-unavailability conclusion.

Process count and memory are now enforced by a delegated transient systemd user
scope (`TasksMax`, `MemoryMax`, zero swap) around Bubblewrap. Per-process address
space, CPU, file, FD, and core rlimits remain inherited. The scope form preserves
the user namespace capabilities Bubblewrap needs; its environment is cleared
before candidate Python starts.

Live hostile probes now pass for hidden home, network denial, read-only system,
minimal deterministic environment, bounded output, and wall timeout. The clean
Python quality fixture passes syntax, isolated tests, strict Mypy, and Ruff.
Canonical Phase 8.2/8.3 artifacts and their integration assertions were replaced
with the corrected evidence. Older handoffs remain unchanged as historical record.
