# ADR 0165: Engineering authority is typed and Core-admitted

Status: Accepted

## Context

FAM_OS can observe owner workspaces, patch a few existing text files, and run a
small set of fixed tools. The next program grants owner-selectable powers for
complete engineering and design work, including deliberately high-risk powers.
Those powers cannot safely be represented by prompt wording, a broad "master"
switch, connector sessions, or model-selected shell access.

The architecture also needs stable records for workspace baselines, proposed
changes, tools, dependencies, design assets, Git delivery, checkpoints, and
evidence before any new provider performs those effects.

## Decision

Core owns the versioned `fam.core.engineering/v1alpha1` contract family. It
admits `EngineeringTaskEnvelope` records and records immutable workspace
snapshots, change-set proposals, file operations, tool recipes and runs,
dependency plans, design manifests, Git operations, checkpoint decisions, and
aggregate evidence. Cross-document validation binds every effect and evidence
record back to its task, proposal, snapshot, recipe, or decision.

Engineering authority is a tuple of visible individual capabilities:
`OBSERVE`, `PROPOSE`, `MODIFY`, `EXECUTE`, `NETWORK`, `PUBLISH`, `RAW_SHELL`,
`HOST_ADMIN`, `SECRET_USE`, `GLOBAL_INSTALL`, `PRODUCTION_MUTATE`,
`POLICY_CHANGE`, `PROTECTED_REF_WRITE`, and `SELF_UPDATE`. Safe policy grants
none of the high-risk capabilities by default, but the owner may explicitly
grant any of them. Authority changes what an admitted provider may do; it never
changes what verification state FAM_OS may claim.

The task envelope binds authority to owner, grant, intent, absolute workspace
roots, permitted operations, path rules, toolchains, network hosts, package
registries, time and mutation budgets, expiry, Git target, and checkpoint
policy. A contract is inert data. Later Core admission and policy components
must validate a live, unexpired, unrevoked grant before dispatch. Concrete
filesystem, process, package, design, Git, network, and privileged effects stay
behind replaceable adapters.

Raw shell authority does not place a model inside a shell or pass it a live
session. Models may propose typed recipes. Core binds an approved recipe to the
task and current workspace, and an adapter executes exact admitted arguments.
Interactive owner terminals remain separate application capabilities. The
privileged deterministic supervisor does not interpret model output.

Candidate workspaces and changeset checkpoints are the default mutation model.
Workspace observation, proposal, modification, execution, publication, and
verification remain separate transactions. External publication requires its
own final checkpoint even when earlier modification was approved.

## Consequences

- Every requested machine power has a precise owner-grantable name without an
  ambient superuser mode.
- Prompt text, repository content, model output, and tool output cannot become
  authority merely by constructing one of these records.
- Providers can be expanded incrementally while sharing stable task, proposal,
  checkpoint, and evidence identities.
- The contract family alone is not runtime authorization. Grant lifecycle,
  result kinds, action-intent admission, signed scopes, Console projection, and
  effect adapters remain required Phase 24–31 work.
- Contract evolution requires a new schema version and explicit compatibility
  or migration policy.

## Alternatives considered

- One hidden "full access" boolean: rejected because it conceals consequences,
  prevents narrow revocation, and makes audit records ambiguous.
- Permanently forbid dangerous owner powers: rejected because the owner is the
  final authority over the machine and this product must preserve that choice.
- Let models invoke a raw shell session directly: rejected because untrusted
  model output would bypass Core admission, checkpoints, postconditions, and
  audit.
- Put engineering policy in filesystem or Git adapters: rejected because
  adapters are replaceable effect mechanisms, not authority owners.

## Evidence

- `src/fam_os/core/engineering/`
- `schemas/v1alpha1/fam.core.engineering-task.schema.json`
- `tests/unit/test_engineering_contracts.py`
- `tests/contract/schema_engineering_fixtures.py`
- `tests/contract/test_cross_contract_references.py`

## Superseded decisions

None. This extends ADRs 0161, 0162, and 0164 without weakening their existing
workspace authority or model-output boundaries.
