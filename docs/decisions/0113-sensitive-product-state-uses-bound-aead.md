# ADR 0113: Sensitive product state uses record-bound AEAD

Status: Accepted

## Context

Prompts, context, authority scopes, action details, memory, connector state, and
adaptation data require local confidentiality. Regenerating a missing key over
an existing database would make old state unreadable while falsely presenting a
healthy new identity.

## Decision

FAM_OS stores one random 256-bit owner master key in a regular, single-link,
mode-`0600` file beneath a mode-`0700` owner directory. AES-256-GCM ciphertext is
authenticated against owner ID, record type, record ID, field name, cipher
version, and bound key ID.

A key is created only when the database path does not exist. Existing database
plus missing, unsafe, malformed, or differently bound key returns explicit
recovery-required state. It never creates replacement key material. The key ID
is transactionally bound in database metadata.

## Consequences

- Moving ciphertext between owners, records, or fields fails authentication.
- Raw SQLite bytes do not contain encrypted plaintext payloads.
- Key loss requires recovery/restore rather than transparent reset.
- Backup and release operations must treat database and owner key as one
  separately protected recovery set.

## Alternatives considered

- Reuse memory-only key injection. Rejected because installed startup needs a
  durable fail-closed lifecycle.
- Encrypt without associated record identity. Rejected because valid ciphertext
  could be substituted between records.
- Automatically rotate when a key is missing. Rejected because it destroys the
  ability to distinguish loss from a new store.

## Evidence

- `src/fam_os/product/storage/keys.py`
- `src/fam_os/product/storage/cipher.py`
- `src/fam_os/product/storage/secure_store.py`
- `tests/unit/test_secure_product_storage.py`
