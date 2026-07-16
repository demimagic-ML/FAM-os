# Trusted multi-device fabric

The Phase 12 fabric requires explicit Ed25519 enrollment and proof of private-key possession. Remote capabilities declare exact package digests and context bounds. Privacy is deny-by-default across owner, device, purpose, workspace, sensitivity, byte count, and raw-content use.

Transport authenticates signed ephemeral X25519 keys, derives session keys with HKDF-SHA256, and encrypts each sequenced envelope with AES-256-GCM. Replays fail. Scheduling considers only trusted, privacy-allowed candidates and compares inference plus network latency. Any disconnect, timeout, partial result, or failed verification discards remote output and retries locally without changing acceptance.

The demonstration uses desktop, laptop, and home-server roles over a real loopback TCP connection. The home-server wins measured policy latency, receives only redacted authorized context, returns a verified result over the encrypted channel, and a simulated disconnect produces verified local fallback.
