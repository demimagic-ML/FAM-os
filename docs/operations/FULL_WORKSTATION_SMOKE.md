# Full-workstation capture and smoke baseline

## Canonical capture

Phase 2.13 captured the reference workstation at:

```text
artifacts/workstation/20260716T113113568743Z/
```

The distributable machine evidence is:

- `host-inventory.json`: strict privacy-reviewed physical inventory;
- `discovered-state.json`: strict live capacity and usage state;
- `effective-budget.json`: strict profile-composed scheduler authority;
- `composition.json`: strict decisions and effective budget;
- `privacy-review.json`: retained, excluded, and opaque field policy;
- `workstation-smoke-20260716-114418-717004.json`: canonical raw smoke report.

The inventory contains hardware and kernel capability, but no hostname, username, home path, mount path, block-device path, serial, GPU UUID/PCI address, or NPU device path. Benchmark source paths retain filenames only.

## Captured authority

The full profile admitted 24 visible logical CPUs with 22 schedulable, 67,017,834,496 bytes physical RAM with 54,132,932,608 bytes schedulable and 12 GiB headroom, a 17,094,934,528-byte RTX 5080 with 14,958,067,712 schedulable bytes and 1 GiB reserve, and a 2,013,991,550,976-byte NVMe root tier with explicit free-space reserve.

Service policy imposed no artificial 16 GiB RAM ceiling, hid no discovered accelerator, and enforced zero service swap. The transient service was inactive after every run.

## Measurement provenance

- CPU time, RAM current/peak, swap, OOM events, and pressure come from the transient service cgroup.
- VRAM capacity, usage, and utilization come from bounded `nvidia-smi` fields without UUID or PCI identity.
- Model-transfer evidence is the fresh service's before/after Ollama resident-set and accelerator-residency delta.
- The delegated user cgroup did not expose `io.stat`; SSD evidence therefore uses root-partition kernel counters. It is labeled `host_root_partition` and `host_activity_during_benchmark_window`, not service-exclusive I/O.
- Latency, load time, token counts, and generation rate come from Ollama inference metrics.
- Candidate failures and deterministic verifier evidence are retained; failed content was withheld.

## Canonical result

The canonical run recorded all seven required evidence categories, zero service swap, zero OOM kills, GPU placement, and 7B-to-14B escalation. The quality check did not pass: seven generated candidates failed the deterministic stable-topological-sort verifier, and FAM released no candidate content.

This is a valid baseline measurement and a failed quality gate, not a successful quality claim. Phase 2's exit gate requires the distinct raw full-capability artifact; future Expert Fabric evaluation owns improving task fitness without weakening verification.

## Strict post-baseline quality rerun

Phase 2.14 preserves the failed baseline and adds a fresh capture at:

```text
artifacts/workstation/20260716T122504578152Z/
```

The repair path now receives an explicitly bounded `RepairContext` containing the
verifier-owned test source and four required input/output examples. Test disclosure
is opt-in policy for this diagnostic benchmark; it is not a default Core behavior
or an unseen-generalization claim. The initial prompt separates the algorithm into
six numbered invariants instead of one overloaded paragraph.

The strict v2 verifier also enforces requirements that the earlier functional
fixture did not: exactly one function, at most 50 lines, no set/set-comprehension,
no calls to `set`, `min`, or `sorted`, and no input mutation. The original parent
parity fixture remains separate so historical functional parity is still reproducible.

Two installed stronger models were run independently so early success could not
skip the second model:

- `workstation-smoke-20260716-122820-440726.json`: Laguna 33.4B Q4 failed its
  initial static conformance check, then passed after one repair. The repair prompt
  contained 1,486 tokens, including the exact failure, trusted tests, and examples.
  Total model residency was 23,523,688,048 bytes, accelerator residency was
  13,483,219,353 bytes, service CPU was 44,237,587 microseconds, zero swap and OOM
  kills were observed, and all smoke checks passed.
- `workstation-smoke-20260716-122945-696264.json`: Gemma 4 25.8B Q4 passed on its
  initial generation. Total model residency was 18,538,393,761 bytes, accelerator
  residency was 12,255,294,913 bytes, peak service RAM was 20,408,229,888 bytes,
  inference wall time was 54.82 seconds, zero swap and OOM kills were observed, and
  all smoke checks passed.

An earlier Laguna diagnostic in the same directory passed the old functional tests
while violating explicit no-set/no-min constraints. It is retained as evidence of
the verifier gap but is not a canonical successful quality result.

## Reproduction

```bash
PYTHONPATH=src:. python3 tools/capture_workstation_resources.py \
  --profile configs/profiles/full-reference-workstation.json \
  --output-root artifacts/workstation
```

Use the returned budget path:

```bash
PYTHONPATH=src:. python3 tools/run_workstation_smoke.py \
  --config configs/benchmarks/full-workstation-verified-smoke.json \
  --trusted-tests tests/fixtures/verification/stable_topological_sort_tests.py \
  --profile configs/profiles/full-reference-workstation.json \
  --effective-budget <capture>/effective-budget.json \
  --output-dir <capture>
```

Use either strict stronger-model fixture to reproduce the post-baseline run:

```bash
--config configs/benchmarks/full-workstation-verified-smoke-laguna.json
--config configs/benchmarks/full-workstation-verified-smoke-gemma4-26b.json
```

## Required future regression

These runs are not disposable diagnostics. Phase 6.6-6.7 and Phase 9 must retain
the original failed stable-topological-sort workload as a named regression and
exercise both installed escalation experts independently:

- `laguna-xs.2:q4_K_M` must retain evidence for its strict initial failure and
  bounded test-informed repair;
- `gemma4:26b` must retain an independent strict run rather than appearing only
  as a fallback that Laguna success can skip;
- both runs must use the full-reference workstation profile and record CPU,
  RAM, VRAM, storage I/O, latency, verifier outcome, and attempt boundaries;
- the strict no-`set`/`min`/`sorted`, input-order, neighbor-only, cycle, and
  no-mutation requirements must not be weakened;
- trusted tests and tricky input/output examples may reach only a repair path
  whose verifier package explicitly allows disclosure.

The models are escalation packages, not automatic defaults. Smaller experts
still run first when benchmark evidence predicts they can satisfy the verified
task.

## Phase 6 installed-package regression

The required package-aware rerun is retained at:

```text
artifacts/workstation/20260716T170632701276Z/
```

Unlike the Phase 2 diagnostic, each report proves an enabled durable package
coordinate, exact Ollama digest, declared `code.generate.python` capability,
escalation tier, runtime adapter, and installation-state revision 17. Laguna
1.0.2 has both a retained strict failure and a successful one-repair run; Gemma
1.0.2 passed independently on its initial attempt. The sibling strict benchmark
metadata documents bind each summary to its raw report digest. Installation,
current/rollback versions, and real rollback/restore evidence live under
`artifacts/expert_fabric/phase6/`.
