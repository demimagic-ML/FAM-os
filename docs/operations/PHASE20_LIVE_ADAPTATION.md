# Phase 20.6 live predictive adaptation

Live adaptation is automatic after two or more independently verified outcomes
exist for one closed intent workflow. It never learns from unverified results and
never sends prompt content in a model-prewarm request.

The installed service derives four bounded signals:

- verified expert frequency for same-tier model tie-breaking;
- P95 context demand with a complete-current-prompt safety floor;
- escalation probability for strong-model readiness; and
- a minimum-two-observation, minimum-0.75-confidence next-expert transition.

Snapshots and prewarm receipts are encrypted in the product database. Rejected
receipts reserve zero bytes. Executed prewarm requires a cold model, live
RAM-plus-VRAM fit with two GiB host reserve, no requested eviction, and confirmed
post-load residency. The Ollama adapter uses an empty `/api/generate` request
with `keep_alive`, then checks `/api/ps`.

## Qualification

Run the signed installed gate:

```bash
PYTHONPATH=src .verification-venv/bin/python -m tools.run_phase20_live_adaptation_exit
```

It creates a signed seven-component release and submits six exact-verifier code
workflows. Two workflows exercise primary failure, repair failure, and real Core
escalation to the configured `gemma4:26b` expert. The fifth verified transition
prewarms Gemma; the sixth request selects that resident strong expert and remains
verified while its context allocation is 2,048 rather than the 32,768 baseline.
Repair requests rise to 4,096 when verifier feedback enlarges the active prompt.
The gate also proves encrypted content absence, restart reconstruction without
inference replay, healthy diagnosis, and complete removal. Evidence is written
to `artifacts/adaptation/phase20.6-live-adaptation.json`.

Run the physical Ollama prewarm gate:

```bash
PYTHONPATH=src .verification-venv/bin/python tools/run_phase20_hardware_prewarm.py
```

This sequentially prewarms the downloaded `gemma4:26b` and
`laguna-xs.2:q4_K_M` models without prompt content, records observed RAM/VRAM
residency, and unloads each model. Evidence is written to
`artifacts/adaptation/phase20.6-hardware-prewarm.json`.

## Failure behavior

Insufficient capacity produces a durable rejected receipt and no runtime load.
Runtime load or residency-proof failure produces a failed receipt; normal
on-demand selection and verification remain available. Prediction cannot evict
work, grant authority, change acceptance, or release an unverified candidate.

User-facing disable, reset, drift, and rollback operations are Phase 20.7 and
remain required before Phase 20 is complete.
