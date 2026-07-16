# Expert Capability Namespace

## Purpose

Phase 6.1 defines one provider-neutral identity space for the abilities declared
by installable `ExpertManifest` packages and live `ExpertDescriptor` instances.
Capability IDs describe what an expert can attempt. They do not identify a
model, grant authority, prove quality, or replace verification.

The namespace contract is `fam.expert.capabilities/v1`.

## Canonical form

A built-in capability has this form:

```text
<domain>[.<operation>[.<qualifier>...]]
```

Every segment is a lowercase token beginning with a letter and containing only
letters, digits, or interior hyphens. IDs are bounded to 128 characters and
eight segments. Whitespace, case folding, aliases, and implicit normalization
are rejected at the manifest boundary.

The initial FAM-owned domains are:

| Domain | Ownership |
|---|---|
| `kernel` | Small FAM intent/planning experts; never Linux kernel execution |
| `routing` | Task classification, complexity, and expert selection hints |
| `language` | General language generation, summary, translation, and transformation |
| `code` | Code generation, repair, review, and explanation |
| `retrieval` | Embedding, reranking, and grounded synthesis |
| `math` | Mathematical reasoning delegated to required deterministic verifiers |
| `application` | Interpretation and planning for Application Fabric tasks |
| `vision` | Image and screen understanding |
| `speech` | Speech recognition and synthesis |
| `safety` | Risk and policy classification assistance |
| `verification` | Untrusted verification assistance, never trusted verifier authority |

Examples include `code`, `code.generate`, `code.generate.python`,
`retrieval.embed`, and `application.plan.editor`.

## Matching

Matching is exact. An expert declaring `code` satisfies a request for `code`
only; it does not automatically satisfy `code.generate.python`. Likewise, a
specific declaration does not imply its parent. Routers may deliberately map a
task to another capability, but that decision must be explicit and auditable.

There are no wildcards, prefix grants, case-insensitive aliases, or model-name
semantics in a capability ID.

## Publisher extensions

Third-party leaves use:

```text
vendor.<publisher-id>.<domain>.<operation>[.<qualifier>...]
```

The publisher segment must be a canonical single token and must exactly match
the package `publisher_id`. This prevents one package from claiming another
publisher's namespace. A capability intended for broad interoperability should
be proposed as a FAM-owned domain leaf instead of copied into multiple vendor
namespaces.

## Trust and verification boundary

Capability declaration is a static package claim. Registry installation,
signature validation, hardware compatibility, benchmark evidence, current
residency, routing selection, and required verifier success are independent
decisions in later Phase 6-9 services.

In particular, `verification.*` experts remain untrusted model participants.
Only Verification Fabric manifests and trusted execution policy can release an
accepted result.

## Manifest versions

- `fam.expert.manifest/v1alpha1` remains frozen and exactly decodable for
  compatibility. It accepted non-empty unique capability strings.
- `fam.expert.manifest/v1alpha2` is the finalized installable manifest and
  requires this namespace.
- `migrate_expert_manifest_v1alpha1` is the explicit migration. It succeeds only
  when every legacy capability is canonical; otherwise package authors must
  choose a valid replacement rather than receiving a silent alias.
