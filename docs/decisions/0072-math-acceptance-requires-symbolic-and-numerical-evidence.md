# ADR 0072: Math acceptance requires symbolic and numerical evidence

**Status:** Accepted  
**Date:** 2026-07-16

FAM requires exact symbolic simplification and declared-domain numerical samples.
Neither alone can authorize release. Expressions enter through an AST allowlist,
and reports bind precision, tolerance outcome, maximum error, and counterexample.
This avoids unsafe parser evaluation and makes approximate claims auditable.
