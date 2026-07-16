# Memory retrieval quality and privacy

Phase 10.7 tests an encrypted three-document Nomic index. Three semantically distinct queries must return their expected document at rank one. A different owner must receive zero hits, and none of the indexed plaintext may appear in raw SQLite bytes.

The passing workstation report has 100% top-1 accuracy, zero cross-owner hits, and zero plaintext leaks. The contract requires at least 80% top-1 accuracy and zero privacy failures.
