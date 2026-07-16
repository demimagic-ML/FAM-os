# Memory user management

Phase 10.5 provides scope-authorized inspection, digest-verified export, atomic correction, and cascading deletion for persistent document memory.

Inspection returns approval/provenance metadata only within exact scope. Export reconstructs ordered chunks and refuses output if the source digest differs from approval. Correction re-embeds content and replaces approval plus all chunks in one SQLite transaction. Deletion removes the document and cascading chunks before issuing its payload-removal receipt.

The live evidence executes the complete lifecycle with Nomic embeddings and finishes with zero remaining chunks.
