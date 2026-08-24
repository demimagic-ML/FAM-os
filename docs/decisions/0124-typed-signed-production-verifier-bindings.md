# ADR 0124: Production verification uses typed declarations and exact signed bindings

**Status:** Accepted  
**Date:** 2026-07-17

## Context

Core already distinguished verified from unverified results, but only exact-text
and deterministic application postconditions were reachable from the installed
product. Python, retrieval, mathematics, and media verifiers existed as
components without a production declaration, activation, execution, or durable
evidence path. Allowing a model to choose or judge its verifier would make
acceptance self-asserted. Loading arbitrary Python entrypoints would also turn a
signed manifest into unrestricted code execution.

Verification must bind the admitted request, immutable plan acceptance ID,
candidate, verifier package, runtime adapter, exact installed implementation,
and final evidence. The Shell must remain an unprivileged client and cannot
import privileged verifier implementation types.

## Decision

Every verifiable request carries a versioned `VerificationDeclaration`. The
declaration selects exactly one bounded typed specification: exact text,
deterministic Python tests, byte-bound retrieval citations, symbolic and
numerical mathematics, or media artifact text. Core parses the Shell's canonical
schema document at its ingress boundary, persists the declaration in encrypted
product storage, and compiles its acceptance ID into the immutable plan.

The production verifier catalog accepts only explicit, built-in package and
runtime entrypoint pairs. Activation verifies the manifest, binding, package
version, and canonical SHA-256 of the installed `fam_os.verification` tree. A
verified signed release upgrades the run's effective trust to `signed`; source
configuration remains visibly `local_unverified`.

Adapters are deterministic and domain-specific:

- exact text compares candidate bytes;
- Python executes the declared source and exact test bytes inside Bubblewrap;
- retrieval accepts only claims whose cited quote is present in the declared
  authorized source bytes;
- mathematics parses an allowlisted AST and requires SymPy equivalence plus all
  declared high-precision samples;
- media reopens a bounded regular file without following a final symlink, binds
  its exact bytes, forwards image bytes to inference, and compares observed text.

Every attempt persists a `VerificationRunRecord`, including failures used for
repair. A passing run becomes acceptance evidence only when its request,
candidate, declaration, acceptance ID, package, adapter, artifact digest, and
plan all agree. Model text never supplies a verifier verdict or changes the
acceptance contract.

SymPy is a base runtime dependency because the production math verifier is part
of the shipped service, not an optional development profile.

## Consequences

- Shell and Console can submit the five domains without gaining verifier or
  application authority.
- Failed Python attempts retain exact trusted test source and sandbox diagnostics
  for bounded repair; successful repair does not erase prior failed evidence.
- Verifier package or binding drift fails activation closed.
- Installed evidence can distinguish signed execution from local source-mode
  development.
- Adding a verifier kind requires a typed schema, an explicit adapter entrypoint,
  production package and binding manifests, tests, and signed installed evidence.

