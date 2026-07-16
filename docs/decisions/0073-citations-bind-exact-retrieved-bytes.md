# ADR 0073: Citations bind exact retrieved bytes

**Status:** Accepted  
**Date:** 2026-07-16

FAM treats citation formatting as insufficient. A releasable retrieval claim
must reference an exact range of a provenance-identified source whose full
content digest and quoted-span digest both match. All claims must verify; partial
success does not silently release rejected claims.
