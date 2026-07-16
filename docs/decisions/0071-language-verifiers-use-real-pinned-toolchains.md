# ADR 0071: Language verifiers use real pinned toolchains

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

JavaScript, TypeScript, and Rust acceptance evidence comes from real installed
language toolchains, not heuristic parsing. TypeScript is pinned by a private
lockfile. Reports preserve individual gates and exact versions. Candidate
execution is denied unless an isolation-aware caller explicitly supplies the
trusted-fixture condition for non-production evidence.

## Consequences

Compiler upgrades are package changes with new evidence. Missing tools fail
closed. Trusted fixture demonstrations do not grant unisolated production
execution authority.
