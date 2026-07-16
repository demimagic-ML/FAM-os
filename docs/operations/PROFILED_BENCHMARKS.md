# Profile-driven Benchmark Operation

## One composition path

Routing, activation, residency-policy comparison, and verified-escalation workloads now consume the same `BenchmarkComposition`:

```text
strict ValidationProfileDocument
  + strict EffectiveResourceBudget
  -> BenchmarkComposition admission
  -> one ProfiledOllamaService
  -> unchanged workload orchestration
  -> profile-identified raw report
```

There is no CPU benchmark service and separate GPU benchmark service. Profile and effective-budget data choose the service envelope, accelerator visibility, placement budget, and report constraints.

## Required inputs

Every workload CLI requires:

- `--profile`: one strict document under `configs/profiles/` or a compatible future profile;
- `--effective-budget`: a strict `fam.hardware.effective-budget/v1alpha1` document composed from that profile and one captured discovery state;
- the workload's existing historical config, trusted tests where applicable, and output directory.

Admission rejects a budget whose `ValidationProfileRef` differs from the profile, exceeds the profile service memory/swap/CPU envelope, or grants accelerator placement while the profile hides accelerators.

Phase 2.13 owns live discovery and the first full-workstation effective-budget artifact. Never substitute a test fixture for published machine evidence.

## Commands

```bash
PYTHONPATH=src:. python3 tools/run_routing_parity.py \
  --config <routing-fixture.json> \
  --profile configs/profiles/full-reference-workstation.json \
  --effective-budget <captured-full-budget.json> \
  --output-dir artifacts/benchmarks
```

```bash
PYTHONPATH=src:. python3 tools/run_activation_parity.py \
  --config <activation-fixture.json> \
  --profile configs/profiles/compat-cpu-16gb.json \
  --effective-budget <captured-compat-budget.json> \
  --output-dir artifacts/benchmarks
```

`run_policy_parity.py` accepts the same profile and budget while retaining three repeated `--config` arguments. `run_verified_parity.py` additionally requires `--trusted-tests`.

## Service translation

`ProfiledOllamaService` translates provider-neutral service intent at the adapter/tool composition edge:

- common host and model-directory environment is always present;
- `deny_all` accelerator visibility adds the CPU-only CUDA, Vulkan, and runtime-library environment;
- `discovered` visibility does not add accelerator-disabling variables;
- service RAM, swap, and optional CPU quota become `ResourceLimits` and are translated by the systemd adapter;
- placement memory, swap, and GPU allowance come from the admitted effective budget.

Core, Scheduler, and Supervisor contracts contain no Ollama or systemd setting. The translation exists only in the benchmark composition adapter.

## Report constraints

Every workload report now includes:

- profile and profile-document IDs;
- profile and effective-budget source paths;
- effective and scheduler RAM plus headroom;
- service RAM and swap envelope;
- scheduler CPU quota;
- accelerator visibility and per-device placement/VRAM budgets;
- storage cache/reserve budgets.

Resource checks compare the observed cgroup snapshot with the selected service envelope. Accelerator activation checks expect CPU-only loaded models for a non-GPU budget and accelerator residency for a GPU-enabled budget.

## Fresh-state and evidence rules

Each workload still starts a fresh transient service, stops any prior service with the same ID, records a cgroup snapshot, and stops the service on exit. Full-versus-compat comparisons must retain identical prompts, context limits, verifier definitions, and result policy. Failed and degraded runs remain evidence.

The service definition proves requested limits, not applied limits. Published evidence must include the observed resource snapshot and, for the full workstation, live GPU/SSD measurements added by Phase 2.13.
