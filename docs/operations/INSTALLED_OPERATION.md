# Installed operation

The production service is `fam_os.product.service`. One owner-scoped process
composes the Core local-chat gateway, Ollama adapter, peer-authenticated Unix
Shell socket, and token-authenticated loopback Console. Local chat releases text
as unverified `completed` output and refuses application contexts, capabilities,
or verification-required requests; application effects remain behind their
separate Core permission and verification workflows.

The live Phase 15 acceptance installs a private release, executes its generated
`fam-service` and `fam-shell` launchers, sends a real request through
`qwen3:1.7b`, verifies GPU residency through Ollama, loads the Console HTML and
all six API sections, sends SIGTERM, verifies clean shutdown, damages a managed
launcher, proves diagnosis catches it, repairs, and completely removes the
installation. Raw content is excluded; only the transcript SHA-256 is retained.

Evidence: `artifacts/product/phase15/installed-operational-acceptance.json`.
