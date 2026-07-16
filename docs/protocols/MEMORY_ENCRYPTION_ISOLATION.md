# Memory encryption and isolation

Phase 10.6 encrypts persistent document content and embedding vectors with AES-256-GCM before SQLite writes. A unique 256-bit key is registered per owner, ciphertext records its non-secret key ID, and owner ID is authenticated as associated data.

The repository decrypts only after selecting the owning row. Missing keys, wrong key IDs, cross-owner use, modified ciphertext, and modified owner metadata fail authentication. Scope metadata remains visible so rows can be routed and authorized without decrypting every payload; source content and vectors are ciphertext.

The evidence database contains neither test plaintext phrase and passes owner round-trip plus cross-owner rejection. Production key persistence should use the OS keyring/credential service; raw key bytes are never serialized in public contracts.
