# Expert efficiency selection

Phase 9.7 compares experts on the same digest-bound simple-QA benchmark and reports three independent ratios:

- quality per artifact byte;
- quality per measured wall second;
- quality per measured joule.

Quality is exact accepted answers divided by case count. Artifact byte counts and digests come from the live Ollama catalog. Each run is a cold-or-current-residency observation and retains its wall time. Energy is trapezoidal integration of raw `nvidia-smi power.draw` samples over that same interval. Every measurement requires at least two power samples; missing telemetry fails the report instead of creating an estimate.

The report selects independently for each metric. It does not combine ratios into an undocumented score, and it does not claim that this small benchmark predicts every workload. Routing may consume these measurements only for the matching benchmark/hardware context.

The workstation evidence compares Qwen3 1.7B, Llama 3.2 3B, and Granite 3.3 2B and preserves every raw power sample in `artifacts/expert_fabric/phase9.7/expert-efficiency-workstation.json`.
