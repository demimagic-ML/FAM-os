# Evidence-based expert evolution

Phase 9.8 turns benchmark history into advisory proposals:

- Split requires at least 20 cases in two task clusters and a quality gap of at least 0.25.
- Merge requires shared clusters, at least 20 cases per slice, and no quality difference above 0.05.
- Retirement requires a replacement to exceed quality by at least 0.10 and meet or exceed quality-per-joule on every compared cluster.

Every proposal names its source evidence slices, requires approval, and has `state_mutated=false`. An evolution report is structurally forbidden from carrying applied proposal IDs. Actual enable/disable/remove operations remain in the package lifecycle and permission boundaries.

Insufficient evidence returns no proposal. This is intentional: package churn is more harmful than retaining an expert while more benchmark evidence accumulates.
