# ADR 0187: Integration recipes are dual-bound to the installed release

Status: Accepted

## Context

The process adapter must not accept an unsigned development recipe, but product
startup previously had no production recipe catalog. Static pre-signed recipes
cannot use the unknown release signing key, while accepting locally generated
keys would weaken the installed release trust boundary.

## Decision

Complete release assembly generates the initial process/API recipe using the
same Ed25519 key that signs the complete release. The recipe is serialized as a
strict `SignedToolRecipe` under `integration-recipes/` in the expert archive.
The release manifest independently signs the complete expert archive digest.

Runtime first verifies the installed release manifest and every component
digest against the persisted release trust root. It then reads only regular
two-component `.json` members under `integration-recipes/`, with per-member,
count, and aggregate byte limits. Each recipe must name the release signer and
pass the normal signed recipe catalog verifier with that release public key.
Duplicate or malformed members fail the catalog closed.

Product process routing is composed only when this installed catalog exists and
passes. Source-tree development and older releases without recipes retain the
Docker backend but do not receive an unsigned process fallback.

The initial recipe runs the fixed candidate entry point
`/workspace/.fam/services/api.py`. Its only placeholder is `{port:api}`, which
the adapter expands exclusively from the exact declared loopback port. Unknown
or undeclared placeholders fail before systemd effects.

## Consequences

- Recipe intent, executable, template, and archive membership are all bound to
  one verified release signer.
- Replacing either the recipe JSON or expert archive is detected at startup.
- Owners can run candidate API code at the fixed entry point only after the
  normal task/grant/permit path; the release recipe does not grant authority.
- Additional languages and service shapes require explicit release recipes and
  verification rather than arbitrary argv.

## Evidence

- `src/fam_os/product/release_assembly.py`
- `src/fam_os/product/composition/integration_recipes.py`
- `src/fam_os/product/service.py`
- `tests/unit/test_installed_integration_recipes.py`
- `tests/unit/test_release_bundle.py`
- `tests/integration/test_process_api_integration_environment.py`
