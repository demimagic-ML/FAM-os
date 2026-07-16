# Handoff 0125: Installed service operational acceptance

**Date:** 2026-07-16  
**Plan step:** Phase 15.1-15.6  
**Status:** Complete  
**Previous handoff:** `0124-master-plan-operational-reopen.md`

Implemented the Core-owned local inference Shell gateway and the missing product
service composition. Corrected installed release layout and interpreter binding,
added the executable `fam-service` launcher, and pointed the generated systemd
unit to it. A fresh isolated installation executed the real `fam-shell`, reached
Ollama `qwen3:1.7b`, observed 2,235,280,915 GPU-resident bytes, loaded Console
HTML and all six authenticated state sections, shut down cleanly, detected
damage, repaired, and removed every installed artifact.

Evidence: `artifacts/product/phase15/installed-operational-acceptance.json`.
Next: finish the operational service soak and full regression gate for Phase 15.7.
