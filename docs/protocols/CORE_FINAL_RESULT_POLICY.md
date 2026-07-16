# Terminal snapshot final-result policy

Only a terminal plan snapshot may enter `FinalResultPolicy`. Release requires
exactly one `release_candidate` reference resolved through a trusted evidence
registry and bound to the same request and plan. Caller-supplied content is never
accepted.

Verified plans additionally require exactly one passing `verification_pass`
record linked to that candidate and covering every acceptance ID declared by the
release predecessor. Missing, failed, cross-candidate, or incomplete acceptance
evidence rejects assembly.

Release may still be withheld when resolved degradation requires confirmation or
withholding. Cancellation, timeout, permission expiry, policy withholding, and
plan failure map to fixed safe structured failures. Withheld and failed results
always contain no content. Failed/repair/escalation candidate references are not
copied into user-facing result evidence.

Evidence registries are fake/in-memory in Phase 4.8. Durable trusted evidence
storage and provider population remain later work.
