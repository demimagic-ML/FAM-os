# ADR 0077: Mixed benchmark binds fixtures, acceptance, and strong runs

**Status:** Accepted  
**Date:** 2026-07-16

## Decision

Cross-family benchmark cases bind immutable fixture digests and exact acceptance
IDs. All five required families must be present. Kernel-only work cannot claim an
expert. The named stable-topological-sort regression retains independent Laguna
and Gemma raw runs bound by package and report digest, regardless of whether each
requires repair.

## Consequences

A report cannot pass by omitting a difficult family, substituting a different
fixture, weakening acceptance, or counting one strong run twice. Repair outcome
and verifier-context disclosure remain visible in expert benchmark metadata.
