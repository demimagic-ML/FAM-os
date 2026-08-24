# Product state encryption and key recovery

Startup resolves the owner key before opening or creating the product database.
No database path means a new key may be created atomically. Any existing database
requires an existing safe 32-byte key file. Once open, the key's derived ID must
match the ID committed to `storage_metadata`.

Normal startup is denied with one of these recovery reasons:

- `master_key_missing_for_existing_database`
- `master_key_corrupt_or_unsafe`
- `master_key_does_not_match_database`
- `master_key_creation_failed`

No recovery path silently creates a replacement. Diagnosis may inspect database
integrity and migration metadata without releasing sensitive payloads. Restoring
normal operation requires restoring the matching key/database set or explicitly
resetting state through a later recovery command with clear data-loss consent.

Every encrypted field uses AES-256-GCM with a fresh 96-bit nonce. Associated data
binds the token to cipher version, owner, record type, record ID, and field name.
Repositories define those values; UI and model output cannot choose them.
