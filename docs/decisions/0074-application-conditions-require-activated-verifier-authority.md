# ADR 0074: Application conditions require activated verifier authority

**Status:** Accepted  
**Date:** 2026-07-16

Application pre/postcondition evidence is accepted only from the exact verifier
ID named by the proposal and admitted by the verifier trust activation boundary.
Provider claims never substitute for Core-side condition evaluation. Any trust,
identity, evidence, audit, or condition failure withholds output and preserves
recovery information where applicable.
