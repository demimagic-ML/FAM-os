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

Phase 23 corrective integration adds an orthogonal result-kind invariant.
Conversation and grounded answers may contain inference output. An action
receipt requires a plan action result plus independent postcondition evidence;
Core replaces the preparation candidate with a deterministic receipt before
release. Denied or failed action plans remain non-executed action proposals, and
capability-unavailable admission outcomes never enter inference. See
`ACTION_INTENT_FIREWALL.md` and ADR 0147.

The final assembler also verifies the action boundary itself. Each execute step
must have one successful action-result reference plus same-capability,
same-permission-grant audit evidence. Verification acceptance without that
execution evidence is rejected as `final.action_receipt_evidence_required`.
Receipt content is derived from the verified capability set rather than from the
candidate text.
