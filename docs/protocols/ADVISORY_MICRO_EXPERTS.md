# Advisory micro-experts

Four deterministic micro-tier packages perform routing, language detection,
safety pattern screening, and complexity classification before larger inference.
They share a fixed-point, reason-coded advice contract. `advisory_only` is
structurally required to be true: no output grants permission, selects a runtime
without scheduler policy, or overrides verification.

The packages are exact Python-module runtime bindings with 64 KiB conservative
resident declarations and no accelerator requirement. The v1 fixture covers all
labels. Each classifier exceeds the 90% gate (the current canonical fixture is
100%), and the report binds the fixture digest. Safety's `no_known_pattern` means
only that its small pattern set found no match; it is never a safety approval.

Evidence: `artifacts/expert_fabric/phase9.2/micro-expert-benchmark.json`.
