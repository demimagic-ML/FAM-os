# ADR 0070: Python release requires four distinct gates

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Python acceptance is the conjunction of safe syntax, verifier-owned unit tests,
strict Mypy typing, and Ruff static analysis. Each produces separate typed
evidence. Missing tooling, analyzer error, sandbox unavailability, or any failure
withholds release. No gate substitutes for another.

## Consequences

Tool defects and candidate defects remain distinguishable. Real maintained
analyzers are used instead of incomplete local imitations. A syntactically valid
candidate can still be withheld for tests, typing, static quality, or isolation.
