# Local frequency and cache learning

Phase 11.1 learns exact per-expert use frequency and verified-use counts from local outcome observations. Profiles are structurally `local_only` and retain total sample count. They complement the existing transition predictor, which learns next-artifact cache candidates from digest-bound access sequences and remains confidence, byte, I/O, concurrency, waste, and OS-reserve bounded.

Frequency is advisory scheduling evidence; failed uses remain counted and cannot be hidden. Cache speculation still requires deterministic admission and never evicts user workload for a prediction.
