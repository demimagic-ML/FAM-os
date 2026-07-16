# Reproducible reference benchmarks

The publication at `artifacts/product/phase14.7/reference-benchmarks.json` binds
each conclusion to its raw source SHA-256 and reproduction command. Results are
never blended across hardware profiles.

## Minimum hardware: compat-cpu-16gb

The canonical constrained run enforced a 16 GiB service ceiling, 14 GiB
scheduler memory, zero swap, and no accelerator. It executed the admitted 3B and
7B experts, rejected Laguna and Gemma when they did not fit, peaked at
6,981,943,296 service bytes, and used zero service swap. This proves safe useful
degradation; it does not claim 26B-model quality on the minimum machine.

## Full reference workstation

The named machine has 24 logical CPUs, about 64 GiB RAM, a 16 GiB RTX 5080, and
a 2 TB NVMe tier. The full profile reserved two CPUs, 12 GiB RAM, 1 GiB VRAM,
and 100 GiB free storage. In the published verified parity run the economical
7B attempt failed its trusted tests and escalation to `gemma4:26b` passed them in
31.76 seconds, with a measured process memory peak of 26,458,853,376 bytes.
This is full-host evidence and is not presented as a 16 GiB result.
