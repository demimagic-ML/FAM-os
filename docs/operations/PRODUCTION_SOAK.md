# Production soak qualification

`tools/run_production_soak.py` defaults to 24 hours and performs live sampling
and effects: `/proc` RSS measurement, filesystem free-space measurement, thermal
sensor reads when the kernel exposes them, fsync plus byte-for-byte storage
readback, and real child-process crash/restart injection. It fails on recovery
mismatch, RSS growth above 16 MiB, temperature at or above 95 C, storage below
1 GiB free, or any readback mismatch.

The checked Phase 14 evidence is a five-minute qualification on the named full
reference workstation. Release candidates should also execute the default
24-hour profile; absence of thermal sensor data is reported explicitly rather
than fabricated.
