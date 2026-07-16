# Application action condition verifiers

Phase 8.7 connects verifier trust activation to the existing application action
safety path. A condition provider can emit evidence only through an allowed
`VerifierActivationDecision` whose verifier ID exactly matches the proposal's
requirement. Denied activation, ID mismatch, provider exception, malformed
evidence, failed precondition, or failed postcondition all become failed evidence.

Core evaluates preconditions before invoking the provider. It independently
evaluates all postconditions after invocation, releases output only for a
provider-verified result with all declared evidence passing, records terminal
audit, and retains compensation metadata when mutation cannot be verified.
Tests cover the full prepare/confirm/execute/verify/audit/release path and both
failure sides.
