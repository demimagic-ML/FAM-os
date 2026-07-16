# Bounded predictive prefetch

## Purpose

Phase 7.10 may warm a likely next artifact only when historical evidence and all
resource bounds agree. Prediction never grants admission by itself. Prefetch
cannot evict resident work, borrow the operating-system reserve, exceed its I/O
range, or continue after its prediction expires.

## Prediction

The v1 predictor counts immediate transitions in digest-bound historical access
sequences. It emits a prediction only when:

- the selected transition appears at least twice;
- observations meet the configured confidence threshold;
- the candidate is in the declared candidate set;
- ties resolve deterministically by artifact identity.

Each result contains transition/outgoing counts, exact confidence, supporting
sequence identities, prediction time, and expiry. No result is safer than a
low-confidence guess, so insufficient evidence returns no prediction.

## Admission bounds

`DeterministicPrefetchAdmissionPolicy` requires a cold observed candidate and
checks all of the following independently:

- requested prefetch byte ceiling;
- physical read-I/O reservation;
- available capacity in the candidate's cache tier;
- host bytes remaining after the prefetch against the OS reserve;
- maximum concurrent prefetches;
- maximum speculative-waste ceiling;
- unexpired prediction;
- zero eviction authority.

Every failed check becomes an explicit reason. Rejected predictions reserve
zero bytes. Admitted decisions still cannot select an eviction.

## Exact-range execution

The Linux adapter accepts only a regular file beneath an owned root and reads no
more than the admitted range using bounded `pread` chunks. It records logical
bytes, process physical-read bytes, and a content digest. The canonical runner
uses a temporary digest-verified clone of the installed Qwen model, evicts that
clone's page cache, prefetches exactly 32 MiB, and then performs the same demand
read. The clone is removed afterward.

## Canonical evidence

```bash
PYTHONPATH=src:. python3 tools/run_predictive_prefetch.py \
  --output artifacts/scheduler/phase7.10/qwen-predictive-prefetch-canonical
```

Two independent canonical sequences—constrained CPU baseline and full GPU
placement—contain Llama followed by Qwen. They produce confidence 1.0 from two
observations. Admission reserves 32 MiB of cache and read I/O while retaining a
12 GiB operating-system reserve and one-prefetch concurrency ceiling.

The live prefetch moved 33,554,432 logical bytes and 33,685,504 physical bytes,
increased observed cache from zero to 33,685,504 bytes, and the subsequent
32 MiB demand read performed zero physical I/O with the same digest. A separate
counterfactual admission request starts with 40 MiB of the 64 MiB waste ceiling
already consumed; the next 32 MiB speculation is rejected with
`budget.maximum_waste_exceeded`. It is a guard proof, not a claim that the live
successful prefetch was wasted.

## Boundary

The transition model predicts only immediate next-artifact access and does not
claim general workload intelligence. Prefetch warms a byte range; it does not
activate an expert, reserve context memory, or bypass normal admission. Longer
horizons, learned predictors, and production waste ledgers require new policy
versions and evidence rather than silent changes to v1.
