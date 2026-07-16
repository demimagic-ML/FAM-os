# Phase 14.1 security review record

## Review status

Independent automated review is complete and its release blockers are fixed.
No external human penetration test has been performed; the machine-readable
report records `human_external_review_completed: false`. This distinction is a
release fact, not a hidden caveat.

The review used Bandit 1.9.4 for Python static analysis, pip-audit 2.10.1 for
published Python advisories, and npm audit for the production VS Code connector
dependency graph. Raw before/after reports live under
`artifacts/security/phase14.1/` and are digest-bound by `security-review.json`.

## Findings and disposition

- `GHSA-537c-gmf6-5ccf` was a high dependency finding against cryptography
  46.0.7. The project floor is now 48.0.1 and the repeat audit is clean.
- Bandit `B310` found unrestricted URL opening. Ollama transport now rejects all
  schemes except HTTP and HTTPS before the opener is called.
- Bandit `B108` reports `/tmp`, `/proc`, and `/dev` literals used as Bubblewrap
  destinations. They are newly created sandbox mount-namespace roots, not host
  temporary-file allocation, so the finding is accepted with this boundary.
- Shell-free subprocess findings are reviewed adapter mechanisms. Executables
  and argv remain bounded by their adapter contracts; no shell is introduced.

## Release interpretation

The automated gate passes only when every high or critical finding is fixed.
An eventual independent human review should consume the threat model, raw tool
reports, protocol ADRs, sandbox probe, update/rollback tests, and multi-user
isolation evidence. Until that review exists, documentation and UI must not
claim third-party certification or a completed penetration test.
