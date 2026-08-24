# Independent Engineering Security Review

This record must be completed and signed by a human reviewer who is independent
of the implementation. FAM_OS and its implementing model may supply evidence,
but may not identify themselves as the reviewer or mark this gate complete.

## Release identity

- Release ID:
- Signed release manifest SHA-256:
- Source commit/object ID:
- Reviewer identity and organization:
- Independence statement:
- Review start/completion time:

## Required review areas

- [ ] Command execution: recipes, raw shell, cgroups, namespaces, AppArmor,
  output/process limits, and external privilege.
- [ ] Dependency and network authority: registries, proxy/fetch boundary,
  package-name confusion, SBOM, licenses, vulnerabilities, and global-state
  separation.
- [ ] Creative-file parsers: SVG active content, PNG/media metadata,
  decompression limits, fonts/licenses, browser capture, and preview checkpoints.
- [ ] Git credentials: opaque broker references, prompting/config/hooks,
  credential persistence, redaction, and provider transport.
- [ ] Remote publication: exact refs/object IDs/diff, protected operations,
  final approval, replay, uncertain outcome, and restart recovery.
- [ ] Self-modification: source-only scope, runtime/trust/policy denial,
  candidate verification, release signing, rollback, and activation.

## Findings

List each finding with severity, evidence, owner, remediation, and retest result.

## Decision

- [ ] Approved with no blocking findings.
- [ ] Rejected due to blocking findings.

The signed review artifact must be stored outside the repository as the source
of truth. Record only its content SHA-256, detached reviewer-signature SHA-256,
reviewer ID, and approved finding IDs in `EngineeringSecurityReview`; never put
private keys, credentials, or sensitive report content in this repository.
