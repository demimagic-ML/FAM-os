# ADR 0117: Worker cgroups derive from the effective resource budget

Status: Accepted

## Decision

Model, verifier, connector, and training workers receive explicit MemoryHigh,
MemoryMax, MemorySwapMax, CPUQuota, and TasksMax values derived from the active
`EffectiveResourceBudget` and a versioned worker-share policy. The full
workstation model worker can use 85% of the 52 GiB scheduler memory budget and
all 20 scheduler CPU cores in the reference contract, while hardware acceptance
proved a 52 GiB maximum, 47 GiB high watermark, 22-core CPU quota, and zero swap
on the current 24-thread host.

Training limits do not authorize training. Admission still requires the Phase
22 user, thermal, pressure, VRAM, and workload gates.

## Evidence

- `src/fam_os/product/worker_budgets.py`
- `configs/supervisor/full-reference-workers.json`
- `tests/unit/test_worker_budgets.py`
- `artifacts/product/phase17/managed-ollama.json`
