# Phase 18 production verifier qualification

Run the signed installed Phase 18.6 gate with:

```bash
.verification-venv/bin/python -m tools.run_phase18_verifier_exit
```

The host needs Python build tooling, Bubblewrap, and access to the dependency
wheel cache or package index. The runner uses an isolated temporary product root
and an ephemeral Ed25519 test key. It does not modify the user's normal FAM_OS
installation.

The gate builds the FAM_OS wheel and dependency wheelhouse, creates a signed
seven-component release, installs it privately, and starts the installed
service. It submits typed exact-text, Python-test, retrieval-citation,
math-equivalence, and media-artifact requests through the authenticated Console
API. The production path must activate the declared binding, execute the real
adapter, persist the run, and release only verified results.

The gate additionally checks that:

- Python repair receives the complete trusted test source and sandbox failure;
- retrieval evidence binds exact authorized source bytes;
- mathematics uses both symbolic equivalence and declared numerical samples;
- media bytes are forwarded with the inference request and rebound by the
  verifier;
- every passing run reports signed effective trust and the exact release,
  signer, package, adapter, candidate, acceptance ID, and artifact digest;
- diagnosis succeeds and the temporary installation is completely removed.

The machine-readable result is written to
`artifacts/verification/phase18-production-verifiers.json`. A valid exit report
has `passed`, `signed_install_healthy`, `media_image_forwarded`,
`all_json_domains_requested_json`, and `complete_removal` set to `true`, with
five verified tasks.

This is Phase 18 installed evidence for one Linux host. Phase 23 still owns the
independent CPU-only and full-workstation matrices.
