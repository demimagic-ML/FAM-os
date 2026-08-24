# Phase 20.1 signed session-memory qualification

Run the signed installed gate with:

```bash
.verification-venv/bin/python -m tools.run_phase20_memory_exit
```

The runner builds a fresh FAM_OS wheel and dependency wheelhouse, assembles an
ephemeral Ed25519-signed seven-component release, installs it privately, and
starts the installed product with a deterministic local inference source.

Two tasks are submitted through one authenticated Console session. A second
Console session then submits an isolation probe. The service is stopped and
started again against the same encrypted durable state for a restart probe. The
runner records only prompt digests and boolean boundary observations, never the
raw generated prompts or Console credentials.

A passing result proves:

- the follow-up prompt receives both prior user and released assistant turns;
- the injected block contains the nonauthority warning;
- supporting conversation and application context precede an explicitly labelled
  current user request, so an earlier assistant answer cannot replace the active
  request;
- the first turn, a different Console session, and the restarted process receive
  no prior-session block;
- the encrypted database contains no plaintext test nonce;
- signed installation diagnosis and complete removal succeed.

Evidence is written to
`artifacts/memory/phase20.1-session-memory.json`. This gate proves bounded
process-only session memory. It does not enable persistent indexing, preferences,
or learning; those remain explicit later Phase 20 steps.
