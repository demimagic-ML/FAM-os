# FAM_OS Master Plan v2 — Verified Engineering and Design Fabric

## Summary

This document is the additive Phase 24+ roadmap for FAM_OS. It preserves all
historical phases and the still-open Phase 21.7 and Phase 23 gates; it does not
imply that the existing release is complete.

The program extends FAM_OS into a full software-engineering and
creative-production system while preserving user sovereignty. FAM_OS may expose
every machine power the owner deliberately chooses to grant, including raw
shell, administrator access, secret use, global installation, production
mutation, policy changes, force-push, and self-update. No model or tool receives
those powers ambiently: Core records the owner's informed grant, scope,
duration, delegation mode, and revocation state before use, and FAM_OS reports
truthfully whether the resulting work was independently verified, explicitly
waived, or merely executed.

Implementation of this plan must also add:

- A minimal pointer from `MASTER_PLAN.md` to this v2 program without changing
  existing statuses.
- ADR 0165 defining typed engineering transactions, changeset approvals,
  candidate workspaces, and the prohibition on raw model-controlled shells.
- Handoff 0188 recording the audit, new plan, affected interfaces, and
  validation.

## Existing Capability Baseline

FAM_OS already has:

- Signed, resource-aware code experts with economical, specialist, repair, and
  Laguna/Gemma escalation tiers.
- Durable Core planning, budgets, approvals, cancellation, restart
  reconciliation, audit, and verified-result policy.
- A native VS Code connector supporting semantic observations, diagnostics,
  preview, edit, save, undo, and independent disk verification.
- Owner-authorized workspace mapping and retrieval.
- Hash-bound atomic modification and exact-byte restoration of up to four
  existing UTF-8 files.
- Fixed, allowlisted, shell-free command execution with approval and exit-code
  postconditions.
- Python verification and component-level JavaScript, TypeScript, and Rust
  toolchain verifiers.
- Sandboxed execution using Bubblewrap, cgroups, output limits, time limits,
  and fail-closed isolation.
- Signed packages, memory, application connectors, MCP, Console/Shell
  presentation, and installed operational evidence.

The missing powers are:

- Creating, moving, renaming, deleting, or changing permissions on files.
- Handling binary and creative assets.
- Multi-changeset, multi-command, resumable engineering workflows.
- Production-reachable broad polyglot build, test, lint, type-check, and
  diagnostic execution.
- Dependency resolution and isolated installation.
- Architecture and UI-design governance.
- Git branching, commits, remote push, and pull-request creation.
- Repository-wide transactional rollback and installed qualification of these
  authorities.

**Completion audit correction (2026-07-19):** The initial Phase 24--30 work
established substantial contracts, adapters, component tests, and an installed
qualification harness, but it did not implement every lifecycle capability in
the goal prompt and it did not wire the engineering fabric into the installed
product composition root. Checked items below retain their narrower completed
scope; newly explicit requirements and production-composition items remain
unchecked. Under ADR 0111, no Phase 24--30 subsystem is production-reachable
merely because its contracts or acceptance fixtures pass. See
`docs/operations/ENGINEERING_COMPLETION_AUDIT_20260719.md` and Handoff 0200.

## Phase 24 — Engineering Authority and Contracts

**Goal:** Define the authority-bearing contracts before granting broader
engineering powers.

- [x] 24.1 Add versioned contracts for `EngineeringTaskEnvelope`,
  `WorkspaceSnapshot`, `ChangeSetProposal`, `FileOperation`, `ToolRecipe`,
  `ToolRun`, `DependencyPlan`, `DesignAssetManifest`, `GitOperation`,
  `CheckpointDecision`, and `EngineeringEvidence`.
- [x] 24.2 Separate `OBSERVE`, `PROPOSE`, `MODIFY`, `EXECUTE`, `NETWORK`,
  `PUBLISH`, `RAW_SHELL`, `HOST_ADMIN`, `SECRET_USE`, `GLOBAL_INSTALL`,
  `PRODUCTION_MUTATE`, `POLICY_CHANGE`, `PROTECTED_REF_WRITE`, and
  `SELF_UPDATE` authorities.
- [x] 24.3 Bind every task envelope to workspace roots, permitted operations,
  path restrictions, toolchains, network/package registries, budgets, expiry,
  Git remote/branch scope, and checkpoint policy.

**Phase 24.1–24.3 evidence (2026-07-18):** Core now owns eleven strict
`fam.core.engineering/v1alpha1` document roots, the complete individual
authority vocabulary, bounded task-envelope scope, schema compatibility, and
cross-document identity validation. These contracts grant no runtime effect by
themselves. See ADR 0165 and handoff 0188.
- [x] 24.4 Add strict result kinds for engineering proposals, verified
  changeset receipts, publication proposals, publication receipts, and
  unavailable capabilities.

**Phase 24.4 evidence (2026-07-18):** Five additional strict engineering
document roots distinguish change-set proposals, independently verified
change-set receipts, separately checkpointed publication proposals,
postcondition-verified publication receipts, and unavailable capabilities.
Their fixed result discriminators cannot be relabeled by model output. See
handoff 0189.
- [x] 24.5 Extend action-intent recognition, signed expert scopes, schemas,
  Console/Shell projections, and integration coverage for every new authority.

**Phase 24.5 evidence (2026-07-18):** Deterministic ingress recognizes all
fourteen authority requirements without granting them; signed code-expert
scopes declare only advisory coverage; Shell and Console distinguish proposals,
verified change receipts, publication proposals/receipts, and unavailable
capabilities; and integration coverage records every authority as
component-tested and not production-reachable. See ADR 0166 and handoff 0190.
- [x] 24.6 Add owner-selectable delegation modes: safe default, workspace
  operator, engineering administrator, and custom/full owner delegation. Every
  mode expands into visible individual capabilities rather than a hidden master
  boolean.
- [x] 24.7 Make high-risk grants target-bound, time-bound, purpose-bound,
  revocable, non-inheritable by default, and explicit about reversibility,
  secret exposure, network reach, verification policy, and maximum resource
  impact.
- [x] 24.8 Add a break-glass grant ceremony for administrator, production,
  verification-waiver, and protected-ref authority. Require the owner to review
  the exact consequences and choose whether approval applies to one action, one
  changeset, one task envelope, or a bounded session.
- [x] 24.9 Preserve truthful assurance independently from user authority. An
  owner may authorize execution without a verifier or may change verification
  policy, but FAM_OS must label that outcome `executed_unverified` or
  `verification_waived`; it may never invent a `verified` result.

**Exit gate:** Fake-driven lifecycle tests prove that prompts, repository
content, model output, and tool output cannot create authority.

**Phase 24.6–24.9 and exit evidence (2026-07-18):** Visible profiles expand to
individual authorities; grants bind exact target, purpose, duration, resources,
reversibility, secrets, network reach, and verification policy; exceptional
authority uses an authenticated exact-consequence break-glass decision; and
execution records distinguish `verified`, `executed_unverified`, and
`verification_waived`. The fake grant lifecycle rejects forged approvals from
prompt, repository, model, and tool sources, and proves revocation, expiry, and
one-action consumption. See ADR 0167 and handoff 0191.

## Phase 25 — Repository Intelligence and Architecture Management

**Goal:** Understand complete repositories and produce decision-complete
technical designs before mutation.

- [x] 25.1 Build a Core-owned bounded engineering planner over workspace
  mapping, semantic search, symbols, references, diagnostics, project
  manifests, dependency graphs, Git state, and architecture rules.
- [x] 25.2 Keep LSPs, Tree-sitter, code-graph services, compiler databases, and
  editor APIs behind replaceable adapters.
- [x] 25.3 Treat repository instructions, comments, generated files, and
  dependency metadata as untrusted context.
- [x] 25.4 Support architecture proposals covering modules, interfaces,
  schemas, migrations, ADRs, dependency direction, security boundaries,
  rollout, and acceptance criteria.
- [x] 25.5 Use an append-only restart-safe task graph with typed steps,
  explicit budgets, termination conditions, and checkpoint boundaries.

**Exit gate:** FAM_OS analyzes an unfamiliar repository, traces an
implementation path, generates a decision-complete architecture proposal, and
identifies affected tests without mutation.

**Phase 25 exit evidence (2026-07-18):** A fake unfamiliar repository bundle
combines bounded workspace, semantic, symbol, relation, diagnostic, manifest,
dependency, Git, and architecture-rule evidence through a replaceable adapter
port. Core traces controller-to-service-to-adapter, identifies the exact test,
and emits all nine required architecture decisions without mutation. The
hash-chained task graph reloads after restart and rejects budget increases,
post-terminal advancement, partial records, and tampering. See ADR 0168 and
handoff 0192.

## Phase 26 — Transactional Workspace Creation and Manipulation

**Goal:** Safely create and transform complete projects through reversible
changesets.

- [x] 26.1 Create an isolated copy-on-write candidate workspace from an exact
  baseline snapshot.
- [x] 26.2 Add typed capabilities for directory creation, file creation,
  patching, moving, renaming, deletion, executable-bit changes, and restoration.
- [x] 26.3 Support text and bounded binary assets while preserving MIME type,
  metadata, provenance, and content digests.
- [x] 26.4 Run candidate changes and verification away from the owner
  workspace.
- [x] 26.5 Present one coherent changeset preview containing paths, operation
  types, diffs or asset previews, risk classification, verification, and
  rollback scope.
- [x] 26.6 After approval, recheck every baseline precondition and atomically
  reconcile the changeset into the owner workspace. On conflict or partial
  failure, preserve user changes and roll back only FAM-owned mutations.
- [x] 26.7 Permit FAM_OS to modify its own source checkout, but never the
  running signed installation, trust roots, active release, or live policy.
  Self-modification must pass the normal build, verification, signed-release,
  update, and rollback lifecycle.

**Exit gate:** FAM_OS creates and evolves a multi-file project, rejects stale
or symlinked targets, recovers from interrupted application, and restores the
complete changeset.

**Phase 26 exit evidence (2026-07-18):** Core now owns strict candidate
artifact, baseline, operation, preview, receipt, and self-update protection
contracts. The filesystem adapter builds a reflink-first isolated candidate
with full-copy fallback, rejects symlinks, performs typed text and binary
operations, and runs shell-free verification inside the candidate. An approved
transaction rechecks every affected owner path, journals atomic per-path
reconciliation, restores a completed or interrupted changeset, and preserves a
concurrent owner edit as `recovery_required`. Source self-edit policy permits
only declared source checkouts and keeps the running signed install, trust
roots, active release, and live policy behind the existing signed release
lifecycle. Focused exit and strict-schema tests pass. See ADR 0169 and handoff
0193.

## Phase 27 — Polyglot Execution, Testing, and Dependencies

**Goal:** Build, run, inspect, and verify software without granting a raw shell.

- [x] 27.1 Replace project-specific fixed commands with signed typed tool
  recipes as the safe default. Add a separate raw-shell capability through
  which model-generated commands may execute only when the owner grants
  `RAW_SHELL` for the exact workspace, identity, duration, environment,
  privilege tier, and task envelope.
- [x] 27.2 Qualify Python, JavaScript/TypeScript, Rust, Go, Java/Kotlin, C/C++,
  shell, HTML, and CSS in the initial installed matrix.
- [x] 27.3 Provide build, test, lint, formatting-check, type-check,
  static-analysis, coverage, packaging, and language-server diagnostic recipes
  appropriate to each ecosystem.
- [x] 27.4 Execute inside transient candidate sandboxes with cgroup limits,
  network denied by default, a sanitized environment, no host home, no inherited
  credentials, disabled Git hooks, bounded artifacts, and complete receipts.
- [x] 27.5 Within an explicitly approved task envelope, allow dependency
  resolution and installation only in isolated project environments and only
  from named registries/domains within byte, time, license, and package-count
  budgets.
- [x] 27.6 Record manifest and lockfile changes, artifact digests, SBOM,
  license results, vulnerability findings, and network destinations. Never
  install globally or mutate the host toolchain.
- [x] 27.7 Promote the existing JS/TS/Rust verifier components and add signed
  production verifiers for Go, JVM, C/C++, shell, HTML/CSS, package integrity,
  and project-specific acceptance suites.
- [x] 27.8 Add an owner-authorized host administration broker. It may use the
  platform's normal sudo, polkit, systemd, package-manager, device, and
  filesystem mechanisms after interactive owner authentication, while keeping
  privileged execution outside model and Core processes.
- [x] 27.9 Support owner-granted global package installation and host toolchain
  changes as distinct administrator changesets with exact package sources,
  predicted effects, rollback or removal plans, and before/after host evidence.
- [x] 27.10 Support secret use at three independently selectable levels: opaque
  credential injection, redacted transformation/use, and direct model-visible
  disclosure. Direct disclosure requires its own explicit grant and cannot be
  inferred from permission to use a secret opaquely.
- [ ] 27.11 Add typed, signed recipes and evidence contracts for runtime
  debugging, stack traces, crash dumps, distributed/local tracing, CPU and
  memory profiling, race detection, leak detection, and performance-regression
  comparison against an exact baseline.
- [ ] 27.12 Add database-engineering contracts and adapters for schema
  inspection, forward and rollback migrations, fixtures, transactional tests,
  consistent backups, restore verification, and failed-migration compensation.
- [ ] 27.13 Add bounded environment orchestration for services, APIs, real
  browsers, containers, local clusters, and integration environments. Bind
  every process, port, image, volume, network, health check, cleanup action, and
  retained artifact to the task envelope.
- [ ] 27.14 Add deployment and infrastructure adapters for systemd, containers,
  Kubernetes, and infrastructure-as-code. Require plan/preview, exact target,
  production-mutation authority, secret references, rollout postconditions,
  monitoring, and rollback or explicit irreversibility evidence.
- [ ] 27.15 Add release-artifact workflows for reproducible creation, signing,
  provenance, SBOM attachment, registry publication, promotion, revocation, and
  release rollback.
- [ ] 27.16 Add secret-reference lifecycle workflows for opaque injection,
  redaction, explicit disclosure, rotation, dependent-service restart,
  postcondition verification, and revocation without recording secret content.

**Phase 27.11 partial evidence (2026-07-19):** Strict request, limit, artifact,
and receipt contracts now cover stack traces, crash dumps, tracing, CPU/memory
profiles, race/leak detection, and exact-baseline performance regression.
Requests bind a signed recipe digest, candidate, sanitized environment, network
policy, collection limits, artifact types, and execution authority. Receipts
cannot pass with a nonzero exit, secret-bearing artifacts, mismatched identity,
over-limit evidence, an unrequested artifact type, a substituted baseline, or a
regression above policy. Two generated schemas and focused contract tests pass.
The existing Ed25519 catalog now admits exact diagnostic-purpose recipes and
rejects kind, digest, network, or environment widening. Eight release-owned
recipe specifications use one normalized target placeholder. A concrete
systemd/Bubblewrap adapter runs real Python diagnostics with cgroup/rlimit
bounds, redacts secret-shaped output, stores mode-0600 digest-bound candidate
evidence, rejects symlink targets, and creates no artifact after output flood.
Performance receipts now bind an integer baseline value to its artifact digest,
parse exactly one POSIX real-time metric, and fail above the approved regression
threshold. A fail-closed qualification matrix requires positive and negative
physical receipts for every diagnostic kind and, for installed proof, one exact
release. The physical focused matrix passes 39 tests after exposing and
repairing a resolve-before-symlink-check bug. The remaining diagnostic kinds still need
real positive/negative qualification and installed product composition, so
27.11 is not checked. See ADR 0175 and Handoffs 0200--0202.

**Phase 27.11 toolchain evidence (2026-07-19):** A signed, read-only mounted,
no-shell helper now collects raw cores only in sandbox tmpfs, emits sanitized
analysis, removes the core before exit, and compiles/runs bounded LeakSanitizer
and ThreadSanitizer fixtures. Separate retained-evidence and transient-file
budgets prevent linkers from widening export limits. Crash/stack, strace,
Python CPU profile, resident-memory profile, LeakSanitizer, and performance all
pass real positive/negative pairs. Host paths and secret-shaped text are
redacted. ThreadSanitizer is nondeterministically unavailable on this kernel
with `unexpected memory mapping`, so no complete qualification matrix or Phase
27.11 check is claimed. The focused diagnostic/schema/sandbox suite passes 55
tests and 349 schemas. See ADR 0176 and Handoff 0203.

**Phase 27.11 race-detection correction (2026-07-19):** The signed helper now
launches ThreadSanitizer through `/usr/bin/setarch x86_64 -R`, removing the
kernel address-layout collision without granting privilege or relaxing cgroup
limits. Clean and deliberately racing C fixtures then passed their expected
positive/negative outcomes ten consecutive times. All eight diagnostic kinds
now have real source physical pairs, and the full focused suite still passes 55
tests. Production composition, installed qualification rows, and both-profile
evidence remain open, so 27.11 stays unchecked. See Handoff 0204.

**Phase 27.11 natural-lifecycle composition (2026-07-19):** Core now derives
local runtime diagnostic kinds and exact candidate targets from durable natural
intent and repository facts, selects only installed release-signed recipes,
performs two live execute-authority checks, persists owner-encrypted requests
and receipts, accounts them in the monotonic task budget, and binds passing
receipt IDs into the same changeset preview as ordinary verifier evidence.
Diagnostic-only requests run without owner mutation; modifying requests repeat
the selected diagnostics against a fresh post-apply clone before commit.
Performance work captures the exact sanitized integer baseline on the pristine
pre-edit candidate and reuses its artifact digest, value, recipe, target, and
natural percentage threshold for candidate and post-apply comparisons. The
release now packages the no-shell helper as a digest-bound expert asset and
resolves it only beneath the verified installed release. Console and Shell
expose read-only diagnostic evidence. Real local tool pairs and focused natural
lifecycle tests pass. Distributed service tracing, a new signed installed
candidate, installed per-kind rows, and both-profile evidence remain open, so
27.11 stays unchecked. See ADR 0218 and Handoff 0253.

**Phase 27.12 contract evidence (2026-07-19):** Four strict schema roots now
bind exact database engine/environment/host identities through external secret
references; ordered forward and rollback SQL artifacts by digest; synthetic
secret-free fixtures; pre-state schema/data digests; backup consistency;
transaction and restore tests; exact postconditions; rollback evidence; and
separate production-mutation authority. Destructive plans cannot omit backup
or rollback, and incomplete receipts cannot claim verified. The focused suite
passes 27 tests and all 353 schemas. Real SQLite and service adapters remain
open, so 27.12 is not checked. See ADR 0177 and Handoff 0205.

**Phase 27.12 candidate SQLite evidence (2026-07-19):** Candidate SQLite is now
explicitly workspace-relative and secret-free, while remote engines retain
opaque secret references. A fifth strict root binds an expiring permit to the
exact approved changeset and host. The concrete adapter computes canonical
typed schema/data digests, creates an encrypted engine-native online snapshot,
applies digest-bound forward migrations and parameterized synthetic fixtures in
one transaction, verifies foreign keys and rollback semantics, rehearses the
declared rollback in reverse, restores the backup into a disposable database,
and compensates the live candidate on post-commit failure. Live cancellation
and revocation checks, replay-resistant state, symlink/hardlink rejection, and
SQLite authorizer denial of host attachment and dangerous engine features are
covered by real positive and hostile tests. The focused contract/adapter suite
passes 38 tests and all 354 schemas. Restart reconciliation, product
composition, real protector integration, installed qualification, both-profile
evidence, and remote engines remain open, so 27.12 stays unchecked. See ADR
0178 and Handoff 0206.

**Phase 27.12 recovery evidence (2026-07-19):** Durable attempt state now records
the exact encrypted-backup identity, digest, size, and relative path before
mutation. A fresh-authority recovery adapter reconciles an interrupted unchanged
attempt or restores a committed-unverified candidate to its exact baseline; it
never replays forward SQL. Verified receipts bind their execution permit, and
explicit rollback requires a different permit plus matching plan, target, prior
receipt, terminal state, and ciphertext. Backup extension/substitution, permit
reuse, and terminal replay fail closed. The focused suite passes 42 tests, all
354 schemas validate, and all 41 architecture tests pass. Core authority-ledger
and authenticated-protector composition plus installed/both-profile evidence
remain open, so 27.12 stays unchecked. See ADR 0179 and Handoff 0207.

**Phase 27.12 Core/composition evidence (2026-07-19):** Core now derives exact
`EXECUTE` and `MODIFY` requests from the plan, candidate, path, changeset, and
zero-network/zero-process resource impact before minting a five-minute permit;
both authorities and permit expiry are rechecked during execution. The SQLite
adapter bounds database, input, and encrypted-backup bytes and uses a progress
handler for cancellation/revocation. Product composition protects backups with
the existing owner-key AES-256-GCM cipher and context-bound associated data.
The expanded focused suite passes 47 tests, all 354 schemas validate, and all 41
architecture tests pass. The factory is not yet reachable from authenticated
Shell/Console and the product lacks a persistent engineering grant/audit path,
so this is source composition rather than installed evidence and 27.12 remains
unchecked. See ADR 0180 and Handoff 0208.

**Phase 27.12 persistent-authority dependency (2026-07-19):** Migration 0029
and the production repository now retain engineering grants, approvals, and
append-only authorization decisions under owner-key authenticated encryption.
Every inserted grant starts reconfirmation-required, and secure storage startup
atomically returns every active grant to that state, preserving visibility while
preventing restart replay of mutation authority. Repository, secure-storage, and
product storage-mode tests pass 9/9. Fresh owner/break-glass authentication,
Shell/Console routes, and database-service binding remain open, so no installed
authority claim or Phase 27.12 completion is made. See ADR 0181 and Handoff 0209.

**Phase 27.12 owner-surface evidence (2026-07-19):** The installed product
composition now creates one encrypted persistent grant repository, one
serialized live authorizer, and one owner authority facade shared by database
engineering, Console, and Shell. Two-minute single-use contexts bind exact
grant or break-glass digests to the authenticated transport session. Console
requires loopback session authentication, same-origin CSRF, exact fields, and
explicit confirmation. Shell adds five strict schema roots over its owner-UID,
mode-0600 Unix socket. Neither surface exposes repository reconfirmation or
grant consumption. Cross-session theft, false confirmation, unavailable
services, strict wire round trips, revocation, inspection, and audit access are
covered; 36 focused tests, 12 existing Shell regression tests, and 39
architecture tests pass. Signed installed execution, both-profile database
evidence, and remote engines remain open, so 27.12 stays unchecked. See ADR
0182 and Handoff 0210.

**Phase 27.12 signed installed lifecycle evidence (2026-07-19):** A dedicated
qualifier builds an Ed25519-signed wheel, installs it into a fresh environment,
and proves the imported module comes from `site-packages`. The real scenario
activates a grant through authenticated Console, executes and verifies an
encrypted-backup SQLite migration through Core's exact `EXECUTE` plus `MODIFY`
admission, retrieves the persistent audit, restarts into
reconfirmation-required denial, freshly reconfirms through the owner-UID Shell,
revokes, and proves later database execution is denied before mutation. Both
declared profile scenario runs pass on one measured 24-CPU, 65,447,104-KiB host
with unlimited current cgroup ceilings. This is signed installed lifecycle
evidence, but not independent hardware or enforced per-profile resource
evidence. PostgreSQL/MySQL adapters also remain open, so 27.12 stays unchecked.
See Handoff 0211 and
`artifacts/engineering/phase27/database-authority-installed-20260719-attempt3.json`.

**Phase 27.12 natural-lifecycle SQLite source evidence (2026-07-19):** Core now
derives exactly one candidate SQLite target and complete ordered
forward/rollback migration pairs from the natural request and repository facts.
It verifies digests, rejects transaction control, preflights forward schema
states under the production authorizer, executes rollback in reverse on a
disposable copy, and requires exact baseline schema/data restoration before
persisting a plan. The real database service then uses fresh `EXECUTE` and
`MODIFY` authority, an encrypted backup, durable recovery, and immutable result
reconciliation to mutate only the candidate. Exact passing database evidence
can verify a database-only task and authorizes the binary database in the same
changeset while private `.fam` journals/backups remain excluded. After owner
approval and apply, a strict post-apply receipt independently reopens the owner
database, binds integrity and exact schema/data digests, and gates local commit;
restart reconstruction and the normal inverse-commit rollback retain the same
evidence. Console and Shell expose owner-scoped read-only database plans,
backups, candidate receipts, and post-apply receipts. The affected suite passes
94 tests, architecture passes 41 tests, and all 414 schemas validate.
PostgreSQL/MySQL composition, a new signed installed release, independently
enforced profiles, soak, and human review remain open, so 27.12 stays unchecked.
See ADR 0219 and Handoff 0254.

**Phase 27.13 contract/admission evidence (2026-07-19):** Four strict roots now
bind service or image identity, argv, loopback ports, candidate volumes, health
checks, dependencies, isolated/denied/allowlisted networking, opaque secret
references, resource impact, retained artifacts, expiry, and mandatory cleanup
to an exact task, candidate, changeset, and host. Core derives `EXECUTE`,
per-host `NETWORK`, and per-reference `SECRET_USE` decisions and mints a
five-minute permit. Expiry/cancellation precede effects, live authority is
rechecked, substituted receipts fail, and cleanup remains available after
revocation only for exact original identities. The 33-test focused/schema suite
and all 39 architecture tests pass. Concrete adapters, durable reconciliation,
product controls, and installed evidence remain open, so 27.13 is not checked.
See ADR 0183 and Handoff 0212.

**Phase 27.13 Docker adapter evidence (2026-07-19):** A no-shell bounded client
now verifies the cached image content ID, forbids pulls and unenforceable
allowlisted egress, launches read-only no-new-privileges containers on an
internal network with explicit PID/memory/CPU/tmpfs bounds, and records each
runtime identity durably. Opaque secrets use ephemeral mode-0600 file mounts
and `_FILE` references; a real daemon inspection proves plaintext absent from
container metadata. Partial failures, cancellation/revocation, replay, exact
cleanup, and restart reconciliation remove only recorded resources. A cached
digest-pinned PostgreSQL 17 container passes its signed `pg_isready` health
recipe and leaves no container/network behind. The focused suite including the
real run passes 39 tests and all 39 architecture tests pass. Loopback exposure
under denied egress, retained artifacts, other environment kinds, product
composition, and installed profile evidence remain open, so 27.13 stays
unchecked. See ADR 0184 and Handoff 0213.

**Phase 27.13 product composition evidence (2026-07-19):** The product now
optionally composes the Docker adapter and Core environment service over the
same persistent engineering authorizer. Only an immutable root-owned Docker
client is accepted; absence or unsafe ownership degrades to unavailable without
breaking startup. A release-owned exact PostgreSQL health recipe is composed,
while the default credential injector denies every secret-bearing plan until a
trusted provider exists. The expanded focused suite passes 42 tests and all 39
architecture tests pass. Owner controls, durable environment discovery,
credential provisioning, installed qualification, and other environment kinds
remain open. See Handoff 0214.

**Phase 27.13 signed installed Docker evidence (2026-07-19):** A dedicated
qualifier builds and signs a wheel, installs it into a fresh environment, and
proves the Docker lifecycle imports FAM_OS from `site-packages`. The
digest-pinned cached PostgreSQL scenario passes under both declared profile
labels, rechecking internal networking, PID/memory/CPU/tmpfs bounds, signed
health, secret plaintext absence from daemon metadata, restart cleanup, and no
leftover resources. The wheel and signer digests plus the measured 24-CPU,
65,447,104-KiB host are retained. These are two installed scenario runs on one
host, not independently enforced profile or second-host evidence. Other
environment kinds and owner controls remain open, so 27.13 stays unchecked.
See Handoff 0215 and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt1.json`.

**Phase 27.13 persistent owner-lifecycle evidence (2026-07-19):** Core now
returns a canonical-plan-digest start result containing the exact cleanup
permit and launch receipt. Migration 0030 stores plans, candidates, permits,
receipts, and append-only lifecycle events as owner-context ciphertext while
indexing only bounded identities and state. Environment IDs are single-use;
terminal cleanup is replay-safe and mints fresh evidence. Product startup never
relaunches: it reconciles exact candidate-recorded Docker identities when the
trusted adapter is available, retains unresolved active state otherwise, and
compensates immediately if launch succeeds but persistence fails. Authenticated
Console session/Origin/CSRF routes and four strict owner-UID Shell roots expose
start, list, inspect, audit, cleanup, and reconcile through one product API;
neither surface can bypass Core grant admission. The focused lifecycle, schema,
Console, Shell, and real-Docker suite passes, as do all architecture tests.
Process/API/browser/local-cluster adapters, retained artifacts, enforceable
allowlisted egress, product secret provisioning, and independently enforced
profile evidence remain open, so 27.13 stays unchecked. See ADR 0185 and
Handoff 0216.

**Phase 27.13 process/API evidence (2026-07-19):** A second concrete backend
now resolves exact `recipe-id@version` coordinates only through the signed
recipe catalog and rejects any argv substitution. Immutable root-owned
executables run with cleared environment and dropped capabilities inside
Bubblewrap user/PID/IPC/UTS/cgroup namespaces, nested in a transient owner
systemd scope enforcing memory, zero swap, task, CPU, stop-time, and IP policy.
Denied mode blocks every IP; isolated API mode allows localhost only. Exact
scope identities persist in the candidate for bounded TERM/KILL cleanup and
restart reconciliation. A real Python HTTP API passed loopback HTTP health,
reported finite cgroup limits, cleaned completely, and left zero FAM scopes.
The provider-neutral router selects homogeneous Docker or process/API plans and
fails closed for mixed graphs or absent backends. Failed transient-service,
one-task, UID-map, and default-stop-timeout experiments are retained in ADR
0186. Release-installed process recipe loading, browsers, mixed local clusters,
dynamic ports, volumes, secrets, retained artifacts, allowlisted egress, and
installed profile evidence remain open, so 27.13 stays unchecked. See Handoff
0217.

**Phase 27.13 installed recipe-trust evidence (2026-07-19):** Complete release
assembly now signs the initial fixed-entry Python API recipe with the release
Ed25519 key and embeds it in the independently manifest-digest-bound expert
archive. Runtime verifies the installed manifest, every component digest,
bounded archive member shape/size/count, exact release signer identity, recipe
payload digest, and recipe signature before constructing the process catalog.
Product composition enables process routing only with that verified installed
catalog; source mode and older releases receive no unsigned fallback. The only
template expansion maps `{port:api}` to the exact declared loopback port; all
other placeholders fail before effects. Positive release/real-API tests and a
wrong-signer fixture pass. Signed installed owner/restart lifecycle evidence
and the remaining browser/cluster/artifact/network matrix stay open, so 27.13
remains unchecked. See ADR 0187 and Handoff 0218.

**Phase 27.13 corrected installed lifecycle evidence (2026-07-19):** The
qualifier no longer places the repository on `PYTHONPATH`; product code for all
scenarios imports exclusively from the newly installed wheel in `site-packages`.
Test-only modules are copied separately. Under both declared profile labels, 18
tests pass for dual release/recipe signature trust and wrong-signer denial,
real cgroup/network-bounded HTTP, real digest-pinned PostgreSQL, encrypted
migration-0030 lifecycle persistence, replay and compensation, authenticated
Console confirmation, owner-UID strict Shell transport, and backend routing.
The passing artifact records exact wheel/signer digests and the 24-CPU,
65,447,104-KiB physical host; no FAM scope, container, or network remains. This
supersedes Handoff 0215's scenario-import method, which set repository
`PYTHONPATH` after its identity probe. The two current runs still use profile
labels on one host rather than independently enforced ceilings, and one real
grant-to-restart chained scenario plus browser/cluster/artifact/network work
remain open, so 27.13 stays unchecked. See Handoff 0219 and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt2.json`.

**Phase 27.13 real installed owner/restart chain (2026-07-19):** A single
installed-wheel scenario now activates an exact persistent task grant through
authenticated Console, starts a real release-recipe-shaped candidate HTTP API
through Core admission, persists the plan/candidate/permit/receipt under
migration 0030, closes secure storage with the scope active, reconstructs the
storage/repository/Core/adapter/product stack, reconciles without relaunch or
grant reconfirmation, and inspects terminal cleanup evidence through the
owner-UID Shell. The exact scope is inactive afterward. Installed attempt 3
runs this plus the prior matrix with no repository `PYTHONPATH`; both profile
labels pass 19 tests and the artifact records the exact wheel, signer, and
physical-host evidence. Profile ceilings remain labels on one host, and real
browser/mixed-cluster/artifact/secret/allowlist work remains open, so 27.13 is
still unchecked. See Handoff 0220 and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt3.json`.

**Phase 27.13 bounded real-browser evidence (2026-07-19):** Homogeneous browser
plans now route through the signed process backend. Root-owned browser
toolchains are accepted only when their full tree digest matches a signed
`ToolchainMount`, then mounted read-only in Bubblewrap. A real headless Chrome
uses an ephemeral profile and loopback-only DevTools inside the bounded user
scope. The new client exposes only bounded return-by-value evaluation and
strict size-bounded PNG capture; exact endpoint, masked/oversized-frame, and
invalid-image fixtures fail closed. Installed attempt 5 passes 24 tests for
each same-host profile label from a fresh wheel without repository
`PYTHONPATH`, and leaves no process scope. The generic release intentionally
does not bind an arbitrary host Chrome installation; a portable signed browser
toolchain package, product owner controls, mixed clusters, artifacts, secrets,
allowlisted egress, and independent profile evidence remain open. Phase 27.13
therefore stays unchecked. See ADR 0188, Handoff 0221, and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt5.json`.

**Phase 27.13 retained-artifact evidence (2026-07-19):** Process and Docker
cleanup/reconciliation now stop exact recorded resources before hashing only
declared candidate-relative regular files. No-follow opens, ancestor checks,
stable inode/size/time checks, the cumulative changed-byte budget, and an
explicit ban on internal integration state fail closed. Receipts use the
existing path plus SHA-256 contract; no implicit copy, export, or publication
authority is added. A real sandboxed API creates a declared artifact and its
expected digest is emitted after teardown. Installed attempt 6 passes 26 tests
per same-host profile label from a fresh wheel and leaves no process scope.
Durable artifact storage/export, mixed clusters, process secrets, allowlisted
egress, and independent profile evidence remain open, so 27.13 stays
unchecked. See ADR 0189, Handoff 0222, and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt6.json`.

**Phase 27.13 process-secret adapter evidence (2026-07-19):** Process, API, and
browser services can now consume bounded opaque values only through read-only
files under `/run/fam-secrets`; argv receives no plaintext and the child gets
only `<KEY>_FILE`. Exact relative secret-root identities are journaled before
asynchronous launch and erased on cleanup, failure, revocation, or restart
reconciliation. Legacy journals normalize to no roots. Bubblewrap shadows the
candidate's whole secret-root directory, preventing sibling discovery. A real
HTTP API consumes an injected file and proves the shadow. Installed attempt 7
passes 33 tests per same-host profile label from a fresh wheel; the broader
environment and architecture suites pass 50 and 41 tests. Product composition
passes a provider to both concrete backends but intentionally defaults to
denial because an authenticated encrypted owner secret repository is still
absent. This is installed adapter evidence, not production secret provisioning;
27.13 stays unchecked. See ADR 0190, Handoff 0223, and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt7.json`.

**Phase 27.13 owner encrypted-secret evidence (2026-07-19):** Migration 0031
now stores owner-scoped secret references as generation-bound AES-GCM
ciphertext with exact tool-key and consumer bindings plus append-only metadata
audit. Provision, rotation, and deletion consume confirmed, two-minute,
single-use, transport-session-bound owner contexts over exact operation
digests; invalid attempts cannot burn valid contexts. Console and three strict
Shell roots expose metadata-only lifecycle controls. Product composition now
supplies the repository directly to Docker and process providers. Installed
attempt 8 proves Console provisioning, exact `SECRET_USE` grant activation,
real signed-recipe API file consumption, restart reconciliation, secret-root
erasure, and Shell terminal inspection. It passes 42 tests per same-host
profile; broader and architecture suites pass 60 and 41. Rotation/deletion
still prevents only future materialization and does not forcibly clean an
already-running environment, while mixed clusters, allowlisted egress,
portable browser packaging, and independent profile evidence remain open.
Phase 27.13 stays unchecked. See ADR 0191, Handoff 0224, and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt8.json`.

**Phase 27.13 atomic active-secret revocation evidence (2026-07-19):** One
mandatory product lifecycle coordinator now serializes environment start
through durable active-state persistence with secret rotation/deletion through
exact cleanup evidence and encrypted mutation commit. Only active immutable
plans declaring the exact reference are drained. Cleanup failure prevents the
secret mutation, and adapter-unavailable composition exposes persisted actives
but fails closed. A threaded regression proves a concurrent start cannot be
missed. The real installed Console chain proves rotation stops the systemd
scope, records terminal evidence, erases the exact process secret root, and
only then advances the encrypted generation. Signed installed attempt 10 passes
47 tests per same-host profile label from a fresh wheel; the broader and
architecture suites pass 48 and 41 tests. Mixed clusters, allowlisted egress,
portable browser packaging, independently enforced profiles, soak, and review
remain open, so Phase 27.13 stays unchecked. See ADR 0192, Handoff 0225, and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt10.json`.

**Phase 27.13 mixed-backend environment evidence (2026-07-19):** Product
composition now selects a journaled composite adapter when both Docker and
process executors exist. It derives backend readiness order from the admitted
service DAG, denies unsafe backend-group cycles, partitions aggregate memory,
CPU, and process limits without duplication, compensates launches in reverse,
continues cleanup across failures, resumes only unfinished evidence-backed
branches after restart, captures retained artifacts once, and emits one exact
receipt. A real fresh-adapter scenario launches a cached digest-pinned Python
container dependency before a signed-recipe API and then removes both runtime
families. Installed attempt 12 passes 52 tests per same-host profile label from
a fresh wheel; broader and architecture suites pass 82 and 41 tests. Product
orphan discovery after simultaneous launch/compensation failure, backend
interleaving/shared networking, allowlisted egress, portable browser packaging,
independently enforced profiles, soak, and review remain open. Phase 27.13
stays unchecked. See ADR 0193, Handoff 0226, and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt12.json`.

**Phase 27.13 intent-before-effect recovery evidence (2026-07-19):** Migration
0032 now AES-GCM stores the exact owner plan/candidate before authorization and
the exact permit through a Core observer before executor entry. Successful
starts atomically commit their intent; pre-permit failures close without an
adapter effect; permitted interruptions recover deterministic Docker
container/network, process scope/secret-root, and mixed branch identities
before normal active reconciliation. Exact `recovery-probed-*` evidence avoids
claiming an absent resource was observed and removed. The installed physical
mixed scenario deliberately omits normal result commit, reopens product
storage, cleans both runtime families, and stores the encrypted terminal
receipt. Pending secret consumers are drained by rotation/deletion or make the
mutation fail closed. Installed attempt 13 passes 67 tests per same-host
profile label from a fresh wheel; broader and architecture suites pass 97 and
41 tests. Owner-visible intent audit, allowlisted egress, portable browser
packaging, independently enforced profiles, soak, and review remain open, so
Phase 27.13 stays unchecked. See ADR 0194, Handoff 0227, and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt13.json`.

**Phase 27.13 owner-visible start-intent audit (2026-07-19):** Authenticated
GET-only Console routes and strict Shell `intent_list`/`intent_inspect`
operations now expose owner-scoped intent state, typed plan/candidate, exact
permit, and terminal recovery receipt without ciphertext, secret values,
connector sessions, or adapter journals. State-dependent Shell validation
requires permits and recovery receipts only where semantically valid. The
installed secret-bearing process chain proves committed intent visibility
through both surfaces without value disclosure; the real mixed recovery chain
proves recovered receipt visibility through Console. Installed attempt 14
passes 67 tests per same-host profile label from a fresh wheel; broader and
architecture suites pass 97 and 41 tests, and all 371 schemas validate.
Allowlisted egress, portable browser packaging, independently enforced
profiles, soak, and review remain open, so Phase 27.13 stays unchecked. See
ADR 0195, Handoff 0228, and
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt14.json`.

**Phase 27.13 allowlisted-egress accounting contract (2026-07-19):** Core now
requires every successful allowlisted start to carry a trusted enforcement
identity, exact approved destinations, transmitted and received byte counts,
the plan's exact byte ceiling, quota state, observation time, and evidence
digest. Quota exhaustion, an unapproved destination, a substituted limit, or
missing evidence cannot produce success; cleanup additionally requires final
accounting, while non-allowlisted plans cannot claim it. Exact
open/observe/close/recover contracts and a length-bounded Unix client now bind
permit, plan digest, host, attachment kind, scope, limit, and expiry while
rejecting substituted or unfinalized responses. The affected and architecture
suites pass and all 374 schemas validate. Docker and process
adapters still deliberately deny allowlisted mode because the external
deterministic broker, bypass/DNS-rebinding protection, restart lifecycle, and
installed qualification are not implemented. This is source contract evidence
only, so Phase 27.13 stays unchecked. See ADR 0196 and Handoff 0229.

**Phase 27.13 signed multi-attachment egress source evidence (2026-07-19):**
The external broker source now authenticates the exact Core UID and unified
cgroup, verifies a device-Ed25519-signed request, mints only a temporary exact
Supervisor grant, journals intent before effects, and emits mandatory
hash-chain audit for open/observe/close/recover. Deterministic adapters create
a Linux namespace/veth/nftables attachment, a verified IPv6-only Docker
internal-network/nftables attachment, or both. All attachment listeners share
one CONNECT-only global-DNS-filtered pre-forward byte quota; expiry, quota
exhaustion, substitution, alternate cgroup, and response-loss paths fail closed
in source tests. Process, Docker, mixed orchestration, persistent device
signing, explicit owner socket opt-in, public-key-only export, and terminal
recovery are wired without giving candidates broker sessions. The root unit
refuses an owner-writable runtime. Focused, wider affected, and architecture
suites pass 93, 169, and 41 tests; all 375 schemas validate. Docker 29.1.3 also
accepted and exactly reported the bounded IPv6-only internal network shape in
an unprivileged compatibility probe, which was removed. No root broker,
namespace, nftables policy, signed installed bypass/quota/restart matrix,
independent profiles, soak, or review ran, so this is not installed evidence
and Phase 27.13 stays unchecked. See ADR 0197, Handoff 0230, and
`docs/operations/INTEGRATION_NETWORK_BROKER.md`. Fresh wheel attempt 15 is
preserved as a deliberate failure because repository-layout schema fixtures do
not exist in a wheel-only runtime. Corrected attempt 16 passes 129 installed
package/source-contract tests under each same-host profile label, while its
artifact explicitly records `source_contract_only` and no installed root
broker; see
`artifacts/engineering/phase27/integration-environment-installed-20260719-attempt16.json`.

**Phase 27.13 natural static-preview source composition (2026-07-19):** A
narrow natural-language request for a static integration preview now enters the
same durable engineering lifecycle instead of stopping at a disconnected
environment API. Core derives an internal `integration-environment` authority
only for the exact admitted task; a deterministic planner selects the
release-signed loopback-only Python HTTP recipe, binds the candidate, port,
health endpoint, changeset, limits, and cleanup policy, and never accepts
model-chosen commands, network access, or secrets. Candidate health and
terminal cleanup receipts are exact changeset evidence. After owner approval,
the product applies transactionally and runs a distinct environment against a
fresh owner-workspace clone before commit. Console and Shell expose both
receipt sets, and replay reconstructs their terminal state. A real temporary
Git integration proves owner unchanged before approval, cleanup before the
checkpoint, apply, fresh post-apply health, commit, and two cleaned
environments. Ninety-three affected tests, 27 schema/Shell/Console tests, 41
architecture tests, and three real installed-process/restart tests pass; all
414 schemas validate. The complete source discovery executes 1,836 tests with
15 expected fail-closed production-verifier failures, no internal errors, and
two skips. This is `source_composed` for one static service only: dynamic port
reservation, natural multi-service/browser/container/cluster attachment,
network and secret ceremonies, PostgreSQL/MySQL integration, signed installed
qualification, independent profiles, soak, and review remain open. Phase
27.13 therefore stays unchecked. See ADR 0221 and Handoff 0256.

**Phase 27.13 fixed-template multi-service source evidence (2026-07-19):** An
explicit natural API, backend, full-stack, or web-service request can now add a
regular root `api.py` to the static plan. Core selects only the new
release-signed `integration.python.root-api@1.0.0` template, assigns a distinct
loopback port, fixes health at `/health`, and orders the static service after
the API. Missing/symlinked entrypoints and port collisions fail before
admission; model argv, network, secrets, volumes, and artifacts remain absent.
The complete natural Git lifecycle proves two candidate services before
approval and two fresh-owner services after apply. A real Bubblewrap/systemd
integration reaches health through both signed templates and removes both
scopes. The affected 124-test matrix and 41 architecture tests pass, all 414
schemas validate, and complete source discovery executes 1,840 tests with the
same 15 fail-closed host-verifier failures, no errors, and two skips. This is a
narrow two-template `source_composed` slice, not general declarative service,
browser, container, cluster, network/secret, remote-database, or installed
qualification. Phase 27.13 remains unchecked. See ADR 0222 and Handoff 0257.

**Phase 27.13 versioned natural service declaration evidence (2026-07-19):**
Candidate `fam.integration.json` can now carry the exact public
`fam.core.natural-integration-declaration/v1alpha1` topology. The closed schema
admits only bounded logical IDs, `python_api`/`static_site` roles, and acyclic
dependencies; commands, recipes, ports, images, network, secrets, volumes,
health policy, budgets, and authorities are structurally absent. Core exposes
that vocabulary—not recipe coordinates—to natural generation, decodes the
result with duplicate-key and exact-version rejection, and maps it to
release-owned templates only when its roles are a subset of admitted owner
intent. The declaration itself enters the changeset, apply, Git commit, and
rollback scope, then is decoded again from the fresh owner clone before
post-apply success. One hundred thirty-four affected tests and 41 architecture
tests pass; all 415 schemas validate. Complete source discovery executes 1,845
tests with the unchanged 15 fail-closed host-verifier failures, no errors, and
two skips. Browser/container/cluster templates, explicit network/secret
ceremonies, port leasing, remote databases, and signed installed qualification
remain open, so Phase 27.13 stays unchecked. See ADR 0223 and Handoff 0258.

**Phase 27.13 signed installed natural service-graph evidence
(2026-07-19):** Fresh signed release
`phase30-natural-integration-20260719-1` installs healthily into an isolated
prefix and loads the versioned declaration, all 415 schema roots, and exact
`integration.python.root-api@1.0.0` plus
`integration.python.static-http@1.0.0` recipes from its installed package. An
installed-package-first runner rejects checkout leakage and passes 100 tests,
including the full natural candidate/apply/fresh-owner/commit path and real
two-service process health and cleanup. The production verifier remains
correctly unavailable because root-owned AppArmor profile `fam-os-userns` is
not loaded, so the durable artifact reports `installed_component_passed` but
does not report overall product passage. Browser/container/cluster natural
composition, race-free port leasing, separate network/opaque-secret ceremony,
remote databases, enforced profile rows, soak, and human review remain open;
Phase 27.13 stays unchecked. See Handoff 0259 and
`artifacts/product/phase30/natural-integration-install-20260719-01/evidence.json`.

**Phase 27.13 natural network/opaque-secret ceremony source evidence
(2026-07-19):** Explicit integration wording can now name canonical
`network access to host:port` destinations and `secret ref` identifiers. Core
keeps them out of the ordinary task grant and `fam.integration.json`, derives a
second exact task/workspace/toolchain grant with a visible 16 MiB ceiling and
opaque-only secret policy, and requires a distinct session-bound owner approval
through Console or Shell. Encrypted proposal record v2 preserves the exact
grant and reads v1 records. Before candidate and post-apply launch, the planner
re-derives the resources from immutable owner intent and rejects any identity,
authority, endpoint, reference, exposure, or budget expansion; only the fixed
Python API role may receive secret refs. Incomplete wording remains blocked.
One hundred thirty-six affected tests and all 41 architecture tests pass.
Complete source discovery runs 1,853 tests with the unchanged 15 fail-closed
host-verifier failures, no errors, and two skips. This is source composition,
not installed/live broker or secret-lifecycle proof; remote databases, other
templates, port leasing, profiles, soak, and review remain open. Phase 27.13
stays unchecked. See ADR 0224 and Handoff 0260.

**Phase 27.12/27.13 natural PostgreSQL service source evidence
(2026-07-19):** The closed natural declaration now admits a `postgresql` role
that Core maps only to the release-owned cached PostgreSQL 17 image digest,
signed `pg_isready` health recipe, 256 MiB ephemeral data volume, bounded
memory/CPU/PIDs, and one opaque password ref. The complete supplemental
resource impact is re-derived before launch, API/PostgreSQL multi-secret graphs
require role-labelled refs, and stable `integration:postgresql` plus
`integration:python-api` consumers work across candidate/post-apply phases.
Console and Shell show the storage ceiling and PostgreSQL binding convention at
the separate resource checkpoint. A real Docker run passes natural planning,
Core `execute`/`secret_use` admission, file-only injection, signed health, and
exact cleanup with no leftover container/network. Docker internal networks did
not produce an observable host binding even when publication metadata was
accepted, so the final template exposes no port and makes no remote-migration
claim. One hundred twenty-one affected tests and all 41 architecture tests
pass; all 415 schemas validate. This is `source_composed` service evidence,
not PostgreSQL migration/backup/restore, MySQL, installed/live, profiles, soak,
or review. Phases 27.12 and 27.13 stay unchecked. See ADR 0225 and Handoff 0261.

**Phase 27.12/27.13 signed installed natural PostgreSQL service evidence
(2026-07-19):** Fresh seven-component Ed25519-signed release
`phase30-natural-postgresql-20260719-2` installs healthily in an isolated
prefix, exposes all 415 schemas and both signed Python integration recipes, and
passes 107 installed-package-first tests with zero failures/errors. The runner
proves FAM_OS imports only from the immutable installed release and repeats the
real digest-pinned PostgreSQL secret/health/cleanup row with no host port or
leftover container/network. The artifact separately records
`installed_component_passed=true` and top-level `passed=false`: production
verification remains unavailable until root-owned `fam-os-userns` is loaded.
This advances the isolated service to `installed_component_tested`, not remote
database migration, live activation, independently enforced profiles, soak,
or human review. Phases 27.12 and 27.13 remain unchecked. See Handoff 0262 and
`artifacts/product/phase30/natural-postgresql-install-20260719-01/evidence.json`.

**Phase 27.12/27.13 isolated PostgreSQL migration lifecycle evidence
(2026-07-19):** Exact candidate forward/reverse SQL pairs now run only against
fixed database `fam_candidate` as physically restricted role `fam_migrator`.
The lifecycle binds current file digests, fresh authority decisions, fixed
service/runtime/permit, encrypted custom backup, baseline and forward
schema/data digests, transaction rollback, exact reverse, repeat forward, fresh
restore, and fresh-owner post-apply repetition into the changeset. Bounded SQL
and backup bytes use fixed Docker stdin commands; no shell, host port, writable
container root, or plaintext host temporary artifact is introduced. Fresh
signed release `phase30-postgresql-migrations-20260719-3` exposes 417 schemas
and passes 119 package-first tests; 129 affected and all 41 architecture tests
also pass. External/production PostgreSQL, MySQL, host-policy passage, profiles,
soak, and review remain open, so 27.12/27.13 stay unchecked. See ADR 0226,
Handoff 0263, and
`artifacts/product/phase30/natural-postgresql-migration-install-20260719-01/evidence.json`.

**Phase 30.1 generated-link workspace admission evidence (2026-07-19):**
Repository observation and candidate cloning now prune a closed set of
generated dependency/build/cache directories before no-link validation. They
never follow or copy those entries, while authoritative source symlinks,
hardlinks, traversal, and candidate tampering remain fail-closed. The selected
real npm/Next.js repository now yields 138 bounded files and a 238-entry
link-free candidate with no `.next` or `node_modules` content. Twenty-three
focused workspace/security tests pass and the current-checkout developer
Console is active on port 8877. This is source/developer proof, not final signed
live qualification; 30.1 stays unchecked. See ADR 0227 and Handoff 0264.

**Exit gate:** Positive and deliberately failing fixtures for every language
prove real toolchains, containment, exact evidence, and fail-closed release.

**Phase 27.1, 27.4, and 27.10 evidence (2026-07-18):** Ed25519-signed typed
recipes are the safe default; semantic tampering fails admission. Raw shell is
a separate exact-command, single-use, expiring, principal/task/workspace/env
authorization and cannot carry host-admin authority. Candidate recipes run in
Bubblewrap with all namespaces unshared, network denied, environment cleared,
host home replaced, Git hooks/config disabled, signed digest-bound toolchain
mounts, systemd cgroups, rlimits, bounded output, and complete receipts. Secret
use now has independently enforced opaque, redacted, and direct-disclosure
levels; direct disclosure requires the grant's explicit disclosure policy and
reviewed-consequence digest, while receipts never contain plaintext. The real
source matrix passes positive and deliberately failing fixtures for all twelve
ecosystems in 38.8 seconds, but is truthfully not installed-release evidence.
See ADR 0170 and
`artifacts/engineering/phase27/polyglot-source-qualification-20260718-attempt2.json`.

**Phase 27 completion evidence (2026-07-18):** The release-owned recipe
specification matrix covers every required gate and generates immutable
Ed25519-signed recipes. Dependency resolution stages allowlisted artifacts,
records before/after manifest and lock digests, exact direct package names,
artifact hashes, SBOM, licenses, vulnerabilities, destinations, byte counts,
and isolated-environment size while forbidding global state. Signed receipt
verification binds each pass to its admitted recipe and containment evidence.
Host administration and global installs cross bounded external Unix-broker
clients only after interactive owner authentication and their distinct grants.
The fresh-venv installed wheel matrix accepted positive and rejected negative
fixtures for all twelve ecosystems under both named engineering workload
profiles; it does not claim full-host utilization. See ADR 0170, Handoff 0195,
and `artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt2.json`.

## Phase 28 — Design and Creative-Asset Management

**Goal:** Manage architecture, UI design, and creative assets as verified
project artifacts.

- [x] 28.1 Add typed design briefs, design tokens, component inventories,
  responsive states, interaction specifications, accessibility requirements,
  and architecture-to-UI traceability.
- [x] 28.2 Add controlled creation and editing of raster images, SVG/vector
  assets, icons, diagrams, animation/media assets, and deterministic format/size
  variants.
- [x] 28.3 Keep generative media models behind signed expert adapters;
  deterministic transforms, metadata stripping, and export belong to bounded
  tool adapters.
- [x] 28.4 Bind every generated asset to its brief, references, model/tool
  identity, prompt digest, dimensions, color profile, license/provenance
  metadata, and source/derived relationship.
- [x] 28.5 Add SVG sanitization, file-format validation, decompression limits,
  hidden-metadata checks, font/license checks, contrast and accessibility tests,
  responsive browser captures, visual regression thresholds, and human preview
  checkpoints.

**Exit gate:** FAM_OS generates a UI design system and creative asset set,
implements it in a web fixture, passes accessibility and visual checks, and
restores the prior design changeset.

**Phase 28 evidence (2026-07-18):** Three strict design document roots bind
briefs, tokens, components, responsive and interaction states, accessibility,
architecture traceability, references, source/derived lineage, signed model or
tool identity, prompt digest, dimensions, color profile, license, provenance,
and human checkpoint. Signed-expert generation and deterministic derivation
write only sanitized candidate assets. SVG active/external content, PNG metadata
and CRC, decompression dimensions, contrast, visual-difference thresholds, and
network-denied responsive Chrome captures are enforced. The web design fixture
passes at 360x640 and 1280x720, applies through the journal, then restores the
original design. See ADR 0171 and Handoff 0196.

## Phase 29 — Git and Collaborative Delivery

**Goal:** Turn verified local changes into controlled collaborative delivery.

- [x] 29.1 Add typed read operations for status, history, blame, branches,
  remotes, and diffs.
- [x] 29.2 Add local actions for branch creation, exact-path staging, commit
  creation, and restoration. Commits bind the approved changeset and
  verification evidence.
- [x] 29.3 Add provider-neutral authenticated adapters for push and
  pull-request creation.
- [x] 29.4 Keep credentials in an external secret broker and never expose them
  to models, prompts, logs, or evidence.
- [x] 29.5 Require a separate final external-action approval for push and PR
  creation showing the remote, branch, commits, complete diff, verification
  summary, and proposed PR title/body.
- [x] 29.6 Deny force pushes, protected-branch direct writes, destructive
  tag/ref operations, credential changes, hidden hooks, and unapproved remotes
  by default. Expose each as a distinct owner-grantable capability with an exact
  remote/ref target, expected old object ID, proposed new object ID, consequence
  preview, and separate publication receipt.
- [ ] 29.7 Add typed local and provider-neutral workflows for fetch, review,
  merge, rebase, conflict resolution, tags, releases, and remote-state
  reconciliation. Each history-changing operation binds expected old and new
  object IDs and preserves recovery refs until verification succeeds.
- [ ] 29.8 Add multi-repository delivery plans with exact repository identities,
  dependency order, per-repository checkpoints, cross-repository compatibility
  verification, partial-publication compensation, and resumable receipts.

**Exit gate:** FAM_OS creates a local branch and commit, pushes to an authorized
test remote, opens a draft PR, and proves denial, replay, and restart behavior
for unauthorized publication.

**Phase 29 evidence (2026-07-18):** Shell-free local Git observation exposes
status, history, blame, refs, remotes, and complete diff digests. Branch,
exact-path stage/restore, and evidence-bound commit actions disable prompting,
global/system config, and hooks. Remote publication uses a provider-neutral
Unix broker carrying only an opaque credential reference and requires a final,
expiring, single-use approval over remote URL digest, refs, expected/proposed
objects, complete diff, commits, verification, and PR text. Exceptional ref
operations require separate protected-ref authority. Durable SQLite consumption
blocks replay after restart. The test provider pushed the exact object to a bare
remote and created a draft PR record. See ADR 0172 and Handoff 0197.

## Phase 30 — Bounded Master Engineering Loop

**Goal:** Compose all engineering powers into one safe, resumable lifecycle.

- [ ] 30.1 Compose the complete lifecycle in the installed product root:
  understand request, inspect
  repository, propose architecture/design, create candidate workspace,
  edit/create assets, run diagnostics/build/tests, repair or escalate, present
  a changeset checkpoint, apply, reverify, commit, and optionally publish.
- [x] 30.2 Allow multiple changeset checkpoints per task while preserving one
  monotonic token, time, command, network, file, and storage budget.
- [x] 30.3 Run safe observations and approved-envelope checks automatically.
  Require one exact approval for each coherent mutation changeset. Preserve
  specified controls for destructive, dependency-network, credential, push,
  and PR boundaries unless the owner deliberately grants bounded unattended
  authority for those boundaries in the task envelope.
- [x] 30.4 Persist task state and receipts so restart resumes observation or
  verification but never reuses mutation or publication confirmation.
- [ ] 30.5 Provide production-reachable Console and Shell controls for the task
  graph, candidate workspace,
  diffs, design previews, test results, dependency provenance, budgets,
  rollback, Git state, and publication approval.
- [ ] 30.6 Add governed documentation and generated-content workflows for
  diagrams, API references, runbooks, changelogs, requirement traceability,
  generated-code ownership, authoritative regeneration, and stale-output
  detection.
- [ ] 30.7 Add incident workflows for diagnosis, evidence preservation,
  remediation, monitored recovery, rollback, and post-incident reporting.
- [ ] 30.8 Require independent code, security, architecture, and design review
  checkpoints where policy selects them; findings are typed, attributable,
  restart-safe, and blocking until resolved or explicitly waived with truthful
  assurance.
- [ ] 30.9 Wire authority admission, repository planning, candidate workspaces,
  execution, dependencies, design, Git, deployment, evidence, and rollback
  through unprivileged Core and the installed service composition. Component
  services and test harnesses are not substitutes for this path.

**Exit gate:** FAM_OS completes greenfield creation, feature development,
refactoring, bug repair, architecture migration, UI redesign, test execution,
rollback, and PR delivery without raw terminal authority.

**Phase 30 component evidence (2026-07-18):** `MasterEngineeringLoop` is an optimistic,
revisioned state machine spanning repository evidence, architecture, candidate,
verification, changeset approval, apply, reverify, commit, final publication
approval, publication, completion, and rollback. All checkpoints share one
monotonic token/time/command/network/file/storage budget. SQLite WAL persistence
survives restart while clearing pending mutation/publication authority; a new
exact checkpoint is required. Auxiliary dependency and design receipts join the
same hash-chained task record. The Console projection exposes task graph,
candidate, checkpoint/diff, tests, dependency provenance, design previews,
rollback, Git, publication, and budgets. This proves the state contract and
projection, not installed composition or executable end-to-end orchestration;
30.1, 30.5, and 30.9 remain open. See ADR 0173, ADR 0111, Handoff 0198, and
Handoff 0200.

**Phase 30 installed control-plane evidence (2026-07-19):** the real
`LocalProductService` now composes an owner-scoped, optimistic WAL engineering
loop under the protected state root and exposes strict authenticated
start/list/inspect/resume controls through both Console and the same-owner Unix
Shell. Start requires an active, restart-reconfirmed, unexpired, exact
task-scoped grant; Core-side transitions recheck that grant. Generic stage
advancement is deliberately not exposed because a client-supplied evidence ID
cannot prove inspection, verification, mutation, publication, or rollback.
This advances 30.1/30.5/30.9 production reachability but does not complete them:
the receipt-driven coordinator and executable end-to-end engineering path remain
open. See ADR 0198 and Handoff 0231.

**Phase 30 governance component evidence (2026-07-19):** governed generated
content now binds candidate, signed generator recipe, source digests, output,
ownership, and authoritative regeneration; deterministic reports detect stale
sources or modified outputs, and satisfied requirement traces require code,
tests, and evidence. Independent code/security/architecture/design review is
typed, attributable, optimistic, restart-safe, and blocking; exact-consequence
owner waivers preserve reduced truthful assurance. Engineering incidents enforce
evidence preservation before diagnosis and record remediation, monitored
recovery or rollback, reporting, and closure in a hash-chained persistent state
machine. This is component evidence only: 30.6--30.8 remain open until installed
composition and master-loop execution. See ADR 0199 and Handoff 0232.

**Phase 30 receipt-driver evidence (2026-07-19):** the product-composed master
loop now has a Core `EngineeringLifecycleDriver` that accepts typed repository
analysis, architecture, candidate, verification, checkpoint, apply, Git,
publication, rollback, and completion receipts; validates their exact task,
candidate, decision, action, status, and approval relationships; consumes
derived budget counters; and revalidates the task grant before every transition.
Raw stage/evidence advancement was removed from the product API. A complete
typed apply/commit/draft-publication path passes, while failed evidence,
mismatched receipts, and revoked grants fail without changing state. 30.1 and
30.9 remain open until an active orchestrator invokes the concrete services to
produce these inputs. See ADR 0200 and Handoff 0233.

**Phase 30 active-preparation evidence (2026-07-19):** installed task start now
atomically persists a digest-bound exact task envelope and acceptance-policy ID;
admission checks lifetime plus workspace, authority, toolchain, network,
registry, Git, and resource containment against the active grant. Confirmed
Console and Shell preparation performs bounded read-only Git/filesystem
observation, untrusted-context repository planning, architecture synthesis, and
isolated candidate creation through the receipt driver. `.git` is excluded from
candidate snapshots and denied to candidate operations. This is a real active
front-half product path, but 30.1/30.9 remain open for generated edits, signed
verification/repair, checkpoint apply, Git delivery, and auxiliary service
orchestration. See ADR 0201 and Handoff 0234.

**Phase 30 natural local-delivery source evidence (2026-07-19):** The active
product path now continues from bounded repository context through a strict
untrusted model plan, Core-bound candidate operations, durable edits, trusted
installed-recipe selection, aggregate signed verification, a complete exact
changeset preview, owner approval, transactional apply, owner-tree
reobservation and reverification, and an evidence-bound replay-safe local Git
commit. Console and same-owner Shell project the same separate grant and
changeset checkpoints. Proposal intent and generated source plans are
owner-key encrypted at rest, including secure migration of earlier plaintext
rows. Source validation passes 118 engineering, 47 Shell, 2 natural lifecycle
integration, 53 contract, 41 architecture, and 18 security tests; all 400
schemas validate. The complete 1,455-test unit run now has exactly eight
failures, all because this AppArmor-restricted host has not loaded the required
root-owned `fam-os-userns` profile and Bubblewrap cannot configure its isolated
loopback namespace. This is `source_composed`, not installed evidence. Optional
publication, explicit rollback, governance/auxiliary composition, remaining
Phase 27/29 capabilities, signed installation, both-profile proof, soak, and
human review remain open; therefore 30.1, 30.5, and 30.9 stay unchecked. See
ADR 0202 and Handoff 0235.

**Phase 30 signed installed ordinary-lifecycle evidence (2026-07-19):** A
fresh seven-component Ed25519-signed release now completes the ordinary local
single-repository lifecycle through both authenticated Console and same-owner
Unix Shell. A real `qwen2.5-coder:7b` generation required one bounded semantic
repair; Core then removed a digest-identical proposed test-file replacement so
the exact approved effects contained only the real `app.py` patch. Both clients
presented separate grant and changeset checkpoints, ran signed candidate and
post-apply verification, applied transactionally, and created exactly one clean
evidence-bound local commit. Service restart reconstructed the committed
Console outcome without replay. This advances 30.1, 30.5, and 30.9 to
`installed_tested` for the ordinary local slice, but does not complete their
full wording: publication, explicit rollback, governance/auxiliary composition,
remaining Phase 27/29 powers, clean-room/both-profile qualification, soak, and
human review remain open. Raw evidence is
`artifacts/product/phase30/natural-local-delivery-20260719-01/evidence.json`.
See Handoff 0236; the checkboxes remain open.

**Phase 30 builder-independent installed evidence (2026-07-19):** The next
signed candidate removes the installation's hidden dependency on the
repository-local builder virtualenv. Stable launchers and service units resolve
the durable base interpreter (`/usr/bin/python3.12` on this host), while all
FAM_OS imports and dependencies come from the immutable active release. That
exact corrected release repeated the complete ordinary Console and Shell
natural-language paths, including both checkpoints, signed pre/post
verification, one effective approved patch, one clean commit, and restart-safe
committed state. This resolves the clean-launcher defect but is not the full
31.2 profile matrix. Direct evidence is
`artifacts/product/phase30/natural-local-delivery-20260719-02/evidence.json`.
See ADR 0203 and Handoff 0237.

**Phase 30 explicit rollback source evidence (2026-07-19):** Successful natural
delivery now exposes an optional third exact owner checkpoint through both
Console and Shell. The checkpoint binds the applied preview and journal, exact
paths, and current FAM-created Git head. Core persists rollback intent before
effect, restores only unchanged FAM-owned state, preserves concurrent owner
changes as recovery-required, and creates a separate replay-safe local rollback
commit without rewriting history. Pre-rollback persisted changesets migrate
only inside their SQLite adapter while public decoding remains strict. A direct
natural integration proves apply, reverify, commit, exact restore, one inverse
commit, and terminal rollback reconstruction; 63 affected unit, contract,
integration, architecture, and security tests pass and all 400 schemas validate.
This is `source_composed`, not signed installed proof. Optional publication and
the other previously named gaps remain open, so 30.1, 30.5, and 30.9 stay
unchecked. See ADR 0205 and Handoff 0239.

**Phase 30 natural publication source evidence (2026-07-19):** The natural
lifecycle now continues from its verified local commit to a separately derived
publication proposal. Core binds a clean non-protected feature ref, exact
commits, complete diff, verification evidence, configured remote URL digest,
and credential-opaque broker observation. The final owner ceremony activates a
distinct five-minute task/ref-scoped `publish + secret_use` grant, persists
intent before effect, pushes only a remotely absent feature ref, records the
draft-change-request receipt, and emits terminal completion. Console, Shell,
restart recovery, durable denial, and replay use this one product path. Fifty
focused tests pass and all 405 schemas validate. At the Handoff 0240 checkpoint
this remained `source_composed`: signed installation, automatic feature-branch creation,
existing-ref reconciliation, governance/auxiliary attachment, and the other
open Phase 27/29/30/31 gates remain. Therefore 30.1, 30.5, and 30.9 stay
unchecked. See ADR 0206 and Handoff 0240.

**Phase 30 automatic feature-branch source evidence (2026-07-19):** Local
delivery now records and authorizes an exact task-derived `fam/...` branch
before effect when work begins on `main`, `master`, `trunk`, `production`, or
`prod`. Restart reconciles only the exact branch and unchanged head; an existing
derived ref is a fail-closed collision rather than an implicit reuse. The real
natural publication integration now starts on `main`, commits on the generated
feature branch, and publishes that exact ref only after the separate grant. All
406 schemas validate and 45 affected tests pass. This removes manual feature
branch preparation from the source path, but signed installed proof,
existing-ref reconciliation, and the other open Phase 27/29/30/31 gates remain.
Therefore 30.1, 30.5, and 30.9 stay unchecked. See ADR 0208 and Handoff 0242.

**Phase 30 natural incident attachment source evidence (2026-07-19):** Real
generation, candidate-edit, candidate-verification, changeset-preview, and
post-apply verification failures now create one deterministic incident from the
task, failure code, and concrete upstream evidence identifiers. The incident is
owner-encrypted in installed composition, restart-reconstructable, queryable by
task, and exposed through authenticated Console plus typed Shell list/advance
controls. A real natural verification-failure integration proves attachment and
restart persistence; Console and Unix Shell tests prove the owner controls. All
406 schemas validate. This is a partial `source_composed` advance: automatic
evidence preservation, diagnosis, remediation, monitored recovery, rollback,
reporting, closure, and signed installed proof remain open. Therefore 30.5,
30.7, and 30.9 stay unchecked. See ADR 0207 and Handoff 0241.

**Phase 30 integrated signed-candidate evidence (2026-07-19):** Wheel
`ec0673085c288be17645a0f08cf7c93030e7287a41dce918166df9915bd48100`
was assembled into the seven-component Ed25519-signed release
`phase30-integrated-20260719-1` and installed healthily in an isolated prefix.
The installed package, with no checkout import, passes 62 affected tests and
contains all 406 schemas plus the rollback, publication, incident-control, and
automatic-branch contracts. The installed host-security probe still fails
closed because root-owned AppArmor profile `fam-os-userns` is not loaded, so a
live production-verifier natural lifecycle was not run and the overall evidence
artifact remains `passed: false`. This is `installed_component_tested`, not
completion of 30.1, 30.5, 30.7, 30.9, or 31.2. See Handoff 0243 and
`artifacts/product/phase30/integrated-source-path-install-20260719-01/evidence.json`.

**Phase 30 trusted review gate source evidence (2026-07-19):** Independently
created review checkpoints can now enter the product only through a trusted
internal adapter boundary that verifies the exact task, candidate, and complete
changeset digest. Once recorded, any open finding blocks ordinary changeset
apply. Review records are owner-encrypted, restart-safe, and visible read-only
through Console and Shell; neither client can submit a checkpoint or claim a
resolution receipt. Fifty-eight affected tests pass and all 406 schemas render.
This is partial `source_composed` evidence: discipline-selection policy, a
signed/human independent reviewer adapter, typed remediation receipt lookup,
truthful waiver ceremony, and installed proof remain open, so 30.5, 30.8, and
30.9 remain unchecked. See ADR 0209 and Handoff 0244.

**Phase 30 generated-documentation gate source evidence (2026-07-19):** The
product loop now accepts documentation receipts only through a trusted internal
boundary that rehashes the exact candidate sources and generated outputs,
validates declared ownership and authoritative regeneration inputs, and rejects
candidate escapes and symlinked paths. Owner-encrypted generation, staleness,
and requirement-traceability records survive restart; an exact stale source or
output blocks changeset apply before mutation. Console and Shell expose the
stored documentation state read-only. Fifty-nine affected tests pass and all
406 schemas render. This is partial `source_composed` evidence: signed generator
recipes and adapters, selection policy, real generation and regeneration
execution, diagram/API/runbook/changelog coverage, and signed installed proof
remain open, so 30.5, 30.6, and 30.9 remain unchecked. See ADR 0210 and Handoff
0245.

**Phase 30 signed installed documentation-generation evidence (2026-07-19):**
`SignedDocumentationRecipe` now binds each generator kind, deterministic adapter,
media type, resource bounds, release signer, payload digest, and Ed25519
signature. Core derives required kinds from admitted natural intent, persists
the exact request before any effect, selects only the verified installed
catalog, and routes generated bytes through ordinary authorized candidate edits
before independently re-hashing the receipt. Diagrams, API references,
runbooks, changelogs, and generated-code manifests ship in signed release
`phase30-governance-20260719-3`. Its isolated installation is healthy, has no
checkout import, exposes all 407 schemas, and passes 74 installed-package tests,
including API documentation through checkpoint, apply, reverification, local
commit, and rollback. The production sandbox probe still fails closed because
`fam-os-userns` is not loaded. Automatic stale regeneration, governance-file
digest binding, complete trace generation, live production-verifier proof, and
final scenario qualification remain open, so 30.1, 30.5, 30.6, 30.9, and 31.2
stay unchecked. See ADR 0211, Handoff 0246, and
`artifacts/product/phase30/governed-documentation-install-20260719-01/evidence.json`.

**Phase 30 typed incident preservation/diagnosis evidence (2026-07-19):**
Natural generation, candidate-edit, candidate-verification,
changeset-preview, and post-apply failures now durably preserve their concrete
upstream evidence identifiers and create a typed diagnosis before returning the
failure. Every incident transition is backed by an immutable digest-bound
receipt stored before state advancement; arbitrary, cross-incident, and
wrong-stage client evidence is rejected. The owner-encrypted receipt chain is
restart-idempotent and visible read-only through natural progress, Console, and
Shell. Fifty-nine affected tests and 41 architecture tests pass, and all 408
schemas render. This is partial `source_composed` evidence created after signed
candidate `phase30-governance-20260719-3`: real remediation, monitored
recovery, rollback attachment, reporting, closure, and signed-installed proof
remain open. Therefore 30.5, 30.7, and 30.9 remain unchecked. See ADR 0212 and
Handoff 0247.

**Phase 30 post-apply failure rollback evidence (2026-07-19):** A failed
post-apply verification now presents a separate exact pre-commit rollback
checkpoint rather than stranding changed uncommitted files. The checkpoint
binds the applied journal, paths, current Git head, empty staging state,
consequences, and owner decision. Core restores only unchanged FAM-owned paths,
records no Git effect, and advances the real incident through typed rollback,
structured report, and closure receipts. Progress and retries reconstruct the
same checkpoint, decision, and receipt chain. Shell and Console distinguish
this required recovery from the optional inverse commit after successful
delivery. Eighty-two affected tests and 41 architecture tests pass; all 408
schemas render. This remains `source_composed`: bounded remediation plus
monitored recovery and signed-installed/live proof are open, so 30.1, 30.5,
30.7, and 30.9 remain unchecked. See ADR 0213 and Handoff 0248.

**Phase 30 bounded repair and final-state changeset evidence (2026-07-19):**
The ordinary natural path now counts a failed signed candidate verification,
records its typed incident, performs one repair under the same remaining
token/time/command/file/storage budget, binds the model plan to the current
candidate, applies durable authorized edits, and reruns the trusted signed
recipe. On success it records remediation, two ordered recovery observations,
report, and closure, then derives one final operation per changed path against
the original owner baseline. Unexpected tool output, in-place entry-kind
changes, duplicate paths, and out-of-budget final state fail closed. Only the
repaired passing verification IDs qualify the exact checkpoint; the original
failure remains incident and budget evidence. A shared Core sanitizer replaces
secret-bearing verifier/tool text with digest-only markers before durable
evidence or inference, redacts private host paths and controls, and the preview
discloses combined executable-mode changes. A real repository integration
proves fail, repair, squash, checkpoint, apply, reverify, one local commit, and
closed incident. One hundred thirty-five affected tests and 41 architecture
tests pass; all 408 schemas render. This remains `source_composed`:
documentation-aware regeneration during repair, an independent later recovery
probe, signed-installed/live proof, and final scenario qualification remain
open. Therefore 30.1, 30.5, 30.6, 30.7, and 30.9 remain unchecked. See ADR 0214
and Handoff 0249.

**Phase 30 governed regeneration and trace evidence (2026-07-19):** Every
documentation policy evaluation now persists its exact required kinds, so an
empty conclusion is distinguishable from missing work. Core re-hashes and
binds ownership, authoritative-regeneration, and prompt-free task-requirement
files to each generation request. If verification-driven repair changes code,
the active natural path derives a new source/governance-bound request, reruns
the installed signed byte producer, edits the candidate, and verifies the final
code plus regenerated output. Old stale receipts and reports remain immutable;
apply requires at least one exact current receipt per output. The final passing
verification also produces a deterministic satisfied or explicitly partial
requirement-to-implementation-test-evidence trace. A real repository
integration proves two code/test versions, stale intermediate API docs,
automatic current regeneration, satisfied trace, checkpoint, apply,
reverification, and local commit. One hundred fifty affected tests and 41
architecture tests pass; all 410 schemas render. This is `source_composed`, not
new signed-installed or live production-verifier evidence. Therefore 30.1,
30.5, 30.6, 30.7, and 30.9 remain unchecked. See ADR 0215 and Handoff 0250.

**Phase 30 policy-selected signed review evidence (2026-07-19):** Every
modifying natural task now persists an exact code review selection; sensitive
intent, paths, formats, and risk codes add security, architecture, and design.
The installed composition loads only an Ed25519 release-signed independently
identified reviewer recipe. Its bounded adapter has no effect authority and
returns a checkpoint bound to the exact task, candidate, complete changeset,
producer, recipe, and selected disciplines. Apply rejects a missing,
mismatched, or blocked checkpoint. Findings can be resolved only by typed
receipts citing Core-held remediation edits and passing verification evidence;
an owner may instead use a separate session-authenticated exact-consequence
waiver that persists before state change and truthfully reports reduced
assurance. Console and Shell expose both checkpoint and immutable evidence. Two
real repository integrations prove signed passage and a blocking security
finding followed by exact waiver, apply, reverification, and local commit.
Seventy-six affected tests and 41 architecture tests pass; all 413 schemas
render. This is `source_composed`, not signed installed or live evidence, and
the Phase 31.5 independent human review remains separate. Therefore 30.5,
30.8, and 30.9 remain unchecked. See ADR 0216 and Handoff 0251.

**Phase 30 independently later recovery evidence (2026-07-19):** A successful
candidate repair now records exactly one recovery observation and leaves the
incident visibly `recovery_monitored` while the exact changeset awaits owner
approval. Only after transactional apply does the ordinary signed
owner-workspace reverifier supply a distinct second observation. Core then
creates the report and closure receipts; retry resumes from one or two
observations without creating a third. A real documentation-aware repair
integration proves distinct candidate and post-apply verification conclusions,
then local commit and closed incident. The exact post-apply failure rollback
branch from Handoff 0248 remains unchanged. This is `source_composed`; signed
installed/live proof of both branches remains open. Therefore 30.1, 30.5,
30.7, and 30.9 remain unchecked. See ADR 0217 and Handoff 0252.

**Phase 30 natural-routing regression evidence (2026-07-19):** Natural
engineering dispatch now yields to an explicit Application Fabric context even
when the request also names a workspace URI. URI-only repository requests still
enter the engineering lifecycle. Ambiguous phrases such as `use the MCP bridge`
remain inference-only unless they name a concrete machine target, and delegated
MCP admission accepts an immediate terminal result without assuming that every
accepted result is an asynchronous task. Focused Application/Shell and MCP
firewall suites pass, including the official MCP stdio protocol test. The
latest complete source discovery executes 1,828 tests with 15 host-security
failures and one intermittent legacy Shell `core_unavailable` error; the latter
passes twenty consecutive isolated repetitions and remains an internal
qualification item rather than an external blocker. This is corrective
`source_composed` evidence only. Phase 30.5 and the complete installed lifecycle
remain unchecked. See ADR 0220 and Handoff 0255.

**Phase 30 natural integration-environment source evidence (2026-07-19):** The
master natural loop now composes a bounded static-web integration environment
through candidate verification, exact preview, owner approval, transactional
apply, fresh owner-workspace reverification, local commit, restart recovery,
and equivalent Console/Shell evidence. Environment health alone is
insufficient: the exact candidate plan, READY receipt, service receipts, and
CLEANED receipt must all match the prospective changeset, and a distinct
post-apply environment must pass before commit. This advances the source
portions of 30.1 and 30.5 without widening authority. It does not prove the
complete Phase 27.13 matrix or a new signed installed/live composition, so
30.1, 30.5, and 30.9 remain unchecked. See ADR 0221 and Handoff 0256.

**Phase 30 natural multi-service source evidence (2026-07-19):** The same
master task can now carry an exact dependency-ordered Python API plus static
site through candidate health/cleanup, preview, approval, apply, fresh-owner
health/cleanup, commit, and durable Console/Shell inspection. Both launch
shapes are release-owned fixed templates; natural language and model output do
not select argv or recipes. This advances the integration slice of 30.1 and
30.5 but remains source-only and deliberately narrow. The full auxiliary
capability graph and signed installed/live composition remain open, so 30.1,
30.5, and 30.9 stay unchecked. See ADR 0222 and Handoff 0257.

**Phase 30 declarative natural service-graph source evidence (2026-07-19):**
The model may now propose an owner-visible versioned service graph as ordinary
candidate content while Core alone chooses installed signed execution
templates and derives ports, health, limits, and authority. The generated graph
is included in the exact owner checkpoint, applied transactionally, re-decoded
from the fresh owner tree, rerun, committed, and reconstructed through the same
master loop. This advances the natural-language design-to-execution bridge in
30.1 and its observable state in 30.5 without creating a command channel. The
full auxiliary graph and signed installed/live composition remain open; 30.1,
30.5, and 30.9 stay unchecked. See ADR 0223 and Handoff 0258.

**Phase 30 signed installed natural service-graph evidence (2026-07-19):** The
API/static graph now passes 100 installed-package-first tests from fresh signed
release `phase30-natural-integration-20260719-1`, including real process health
and cleanup, exact recipe identity, all 415 schemas, and checkout-leakage
rejection. Installation diagnosis is healthy. This advances the installed
integration slice of 30.1 and 30.5, but the host production verifier correctly
fails closed while `fam-os-userns` is absent and the live service remains
untouched. It does not supply the remaining Phase 27/29 capability graph,
production-verifier lifecycle, complete Console/Shell controls, or final
qualification, so 30.1, 30.5, and 30.9 stay unchecked. See Handoff 0259 and the
signed installed evidence artifact.

**Phase 30 separate natural integration-resource checkpoint evidence
(2026-07-19):** The master task now presents exact network destinations,
opaque secret references, transfer ceiling, and grant digest as a separate
Console/Shell checkpoint before the ordinary task grant. The approved grant is
owner encrypted, restart-reconfirmable, revalidated against original intent,
and supplied to the same candidate and fresh-owner integration lifecycle. This
removes the blanket rejection for exactly specified network/secret integration
intent without widening model, declaration, or ordinary task authority. The
new branch remains source-composed and has no signed-installed/live broker
proof, so 30.1, 30.5, and 30.9 remain unchecked. See ADR 0224 and Handoff 0260.

**Phase 30 signed live natural-CLI edit/create/run evidence (2026-07-19):**
Fresh signed release `fam-os-natural-engineering-20260719-10` is healthy and
active on port 8877. Two ordinary prompts entered through the installed
same-owner `fam-shell`, not a direct API or mock. The first inspected and edited
a disposable clone of the selected Next.js repository; the second created a
new ES-module implementation and Node test suite. Both flows presented separate
grant and exact changeset checkpoints, passed candidate verification, applied
transactionally, passed fresh owner-tree reverification, created task-derived
feature branches and clean local commits, offered exact rollback, and ended in
verified terminal receipts when the owner chose to keep the commits. An
independent terminal `npm test` rerun passed. The installed sandbox now uses an
explicit AppArmor/Bubblewrap/systemd boundary, and Shell projections permit
only append-only optional steps rather than hiding a successful commit behind a
generic reducer error. Fifty-eight affected, eleven adversarial/transactional,
and all 41 architecture tests pass. This is direct installed evidence for the
edit, create, execute, verify,
checkpoint, apply, reverify, commit, and optional-rollback-decision slice of
30.1/30.5/30.9. A deliberately exercised live repair/escalation branch,
separately approved publication, and the full exit scenario matrix remain open,
so the checkboxes stay unchecked. See ADRs 0228-0229, Handoff 0265, and
`artifacts/product/phase30/natural-cli-acceptance-20260719-01/evidence.json`.

**Phase 30 ChatGPT-authenticated Codex provider evidence (2026-07-19):**
ADR 0230 composes an optional `codex-subscription` provider only at the
chat-only candidate-generation port. Codex retains its own ChatGPT OAuth
session; FAM_OS does not read, copy, translate, or persist that material.
Generation uses an ephemeral `codex exec` process with user configuration,
repository rules, web search, approvals, and model tool activity disabled.
Ollama remains the local residency, catalog, embedding, and offline runtime.
Signed release `fam-os-natural-engineering-20260719-12` is active on port 8877
with `gpt-5.6-sol`. Through installed `fam-shell`, one ordinary prompt analyzed
a disposable Python repository, added `multiply`, added positive, negative, and
zero tests, passed four candidate tests, displayed the exact two-file
changeset, applied after the second owner approval, passed four fresh
post-apply tests, and created clean local commit
`43aea1e2afa9546bec4e2c2b4e10af43d12b184e`; an independent terminal rerun also
passed all four tests. The first live attempt exposed a real scanner defect:
verifier-created `__pycache__` was mistaken for an unauthorized model edit.
Candidate final-state scans now exclude the same non-authoritative cache trees
as owner baselines, with a regression test. Seventy-six focused/polyglot and
all 41 architecture tests pass. This materially advances 30.1 and 30.9 but
does not close their remaining live repair, publication, scenario-matrix,
both-profile, soak, or human-review gates. See Handoff 0266 and
`artifacts/product/phase30/codex-subscription-acceptance-20260719-01/evidence.json`.

**Phase 30 conversational plan and verifier-routing evidence (2026-07-19):**
ADRs 0231-0232 and Handoff 0267 bind explicit plan follow-ups to the same owner,
authenticated session, and canonical workspace while deriving authority only
from the current message. Recognized manifests now dominate engineering
toolchain selection, preventing unrelated utility files from imposing absent
test suites. Signed release `fam-os-natural-engineering-20260719-13` completed a
real authenticated Console HTTP sequence: plan-only repository analysis,
`Ok, implement the plan`, Node-only candidate verification despite an unrelated
Python file, exact changeset approval, apply, post-apply verification, and clean
commit `ed860c64bff46734f56f7981eb445150fe3810e2`. Three independent Node tests
passed. This materially advances 30.1, 30.5, and 30.9, but restart-persistent
plan references, zero-test acceptance policy, installed repair/escalation,
publication, and the complete scenario matrix remain open; the checkboxes stay
unchecked. See
`artifacts/product/phase30/natural-plan-followup-acceptance-20260719-01/evidence.json`.

## Phase 31 — Security and Installed Qualification

**Goal:** Prove the complete engineering fabric from signed installed artifacts
under adversarial and long-running conditions.

- [x] 31.1 Add adversarial coverage for prompt injection in repositories,
  malicious build files, package-name confusion, compromised registries,
  symlink/hardlink races, archive traversal, fork bombs, output flooding,
  secret discovery, data exfiltration, malicious SVG/media, Git-hook execution,
  submodule escapes, stale approvals, and restart replay.
- [ ] 31.2 Requalify both hardware profiles and every dependency profile from
  built signed artifacts.
- [x] 31.3 Run installed end-to-end fixtures for all supported languages,
  design assets, dependency resolution, candidate workspaces, Git delivery,
  restart recovery, and self-hosted FAM_OS source modification.
- [ ] 31.4 Run a minimum 24-hour mixed engineering/design pressure soak with
  interruptions, rollback, model eviction, compiler workloads, dependency
  failures, and candidate cleanup.
- [ ] 31.5 Require an independent human security review specifically covering
  command execution, dependency/network authority, creative-file parsers, Git
  credentials, remote publication, and self-modification.
- [ ] 31.6 Update `configs/integration/coverage.json` only from direct installed
  evidence.

**Phase 31.6 direct partial evidence (2026-07-19):** The coverage contract now
represents `source_composed` and `installed_tested` without confusing either
with operational completion. The corrected signed Console/Shell artifact
advances exactly `observe`, `propose`, `modify`, `execute`, and the candidate
workspace to `installed_tested`; ten specialized engineering authorities
remain component-only and every unproven scope remains in `known_gaps`.
Program status stays `integration_incomplete`, so 31.6 remains unchecked. See
ADR 0204, Handoff 0238, and
`artifacts/product/phase30/natural-local-delivery-20260719-02/evidence.json`.

**Exit gate:** Every new subsystem is `operationally_proven`; no claim depends
only on source tests or acceptance harnesses.

**Phase 31 partial evidence (2026-07-18):** A trusted exact-test ledger covers
all sixteen adversarial categories; the direct installed suite exercises
repository injection, signed-recipe tampering, package confusion/registry
scope, symlink/hardlink/archive attacks, fork/output pressure, secret and
network isolation, malicious SVG/media, Git hook/submodule denial, stale
approval, and restart replay. A fresh venv imported the newly built
Ed25519-signed wheel from `site-packages`, ran positive and deliberately failing
fixtures for all twelve ecosystems under both bounded engineering workload
profiles, and passed 89 installed engineering/design/dependency/candidate/Git/
restart/self-hosted/schema tests in 87.57 seconds. Physical installed runs from
the same checkout pass the constrained and full-workstation profile bodies and
preserve the owner service, but the aggregate strong Python verifier remains
correctly unavailable until an owner administrator loads `fam-os-userns`.
Therefore 31.2, 31.4, 31.5, 31.6, and the exit gate remain open. See ADR 0174,
Handoff 0199,
`artifacts/engineering/phase31/signed-installed-engineering-20260718-attempt3.json`,
and `artifacts/engineering/phase31/hardware-matrix/phase31-engineering-hardware-20260718-04/installed-hardware-matrix.json`.

## Test and Acceptance Requirements

- Every new public contract has strict schema, duplicate-key rejection,
  compatibility, migration, and cross-contract tests.
- Every mutation has stale-baseline, partial-failure, cancellation, restart,
  rollback, and audit tests.
- No owner-workspace mutation occurs before changeset approval.
- No external publication occurs before its separate final approval.
- Model output, repository text, compiler output, package metadata, and design
  files never grant authority.
- Failed builds, tests, security checks, postconditions, or visual/accessibility
  gates cannot produce a verified receipt.
- Raw shell, administrator access, secret disclosure, global package
  installation, unrestricted network access, production mutation, force-push,
  verification-policy changes, and direct FAM_OS self-update are unavailable by
  default but become legal only through their exact owner-granted authorities.
- Revocation prevents future use immediately. Restart never recreates or widens
  an expired, consumed, or revoked high-risk grant.
- Owner-granted power changes what FAM_OS may do, never what FAM_OS may claim.
  Unverified or verification-waived work cannot be labeled verified.

## Assumptions and Defaults

- `MASTER_PLANv2.md` is an additive companion beginning with Phase 24;
  `MASTER_PLAN.md` remains authoritative for Phases 0–23 and their open gates.
- Changeset checkpoints are the default approval model.
- The owner is the final authority over the machine and may deliberately expand,
  restrict, automate, or revoke any FAM_OS capability through visible policy.
- Safe defaults are product defaults, not permanent restrictions on the owner.
- Dependency installation may run automatically only inside the exact approved
  task envelope and isolated candidate environment.
- Local Git branch/commit operations are permitted by the envelope; push and PR
  creation require separate final approval.
- Full creative assets include raster, vector, diagrams, UI assets, and bounded
  media variants.
- Existing Phase 21.7 and Phase 23 blockers remain visible and are not completed
  or waived by adopting this plan.
