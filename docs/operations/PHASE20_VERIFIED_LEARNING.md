# Phase 20.5 verified-outcome learning and terminal retention

Verified-outcome recording is automatic in the installed FAM_OS service. There
is no model tool and no application capability that can write a learning record.
The production terminal policy creates one only after the released result and
its passing acceptance evidence agree.

For every completed request, FAM_OS retains the final user-visible result in the
owner-encrypted product database. It then removes terminal working material that
is no longer needed:

- the durable request prompt and nested application request prompt;
- the action proposal's copy of that prompt;
- primary, repair, escalation, and fallback candidate text;
- verbose verifier feedback; and
- the terminal verification declaration.

The final result, citations, verifier status and digest facts, package trust,
action results, and acceptance evidence remain available. Unverified results are
still readable after restart but never produce a learning observation.

The learning record exposes only the intent workflow, selected expert and tier,
coarse context-token bucket, escalation flag, timestamp, evidence identities,
and a safe evidence digest. Phase 20.6 now connects those records to bounded live
predictors; Phase 20.7 adds user-facing inspection and reset controls.

## Installed qualification

Run:

```bash
PYTHONPATH=src .verification-venv/bin/python -m tools.run_phase20_learning_exit
```

The gate builds and signs a seven-component release, installs it privately, and
submits one verifier-passed request and one unverified request through the
installed Shell transport. It proves exactly one content-free learning record,
zero unverified learning records, terminal normalization, encrypted-at-rest
nonce absence, concurrent-safe terminal retention, restart result retrieval
without another inference call, healthy diagnosis, and complete removal. Raw
evidence is written to
`artifacts/adaptation/phase20.5-verified-learning.json`.

## Failure behavior

Terminal result retention, learning insertion, and redaction share one immediate
transaction. If any write fails, none of them commit. A retry can therefore use
the still-intact working records. If a terminal result already exists, exact
replay returns it and does not create another learning observation.
