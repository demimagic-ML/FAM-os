# Phase 22 Real Expert Factory implementation plan

## Purpose

Phase 22 replaces the Phase 13 demonstration classifier with a production-local,
owner-governed factory for small LoRA or QLoRA specialists. The factory may
discover repeated verified failures and prepare proposals automatically. It may
not retain task content, generate training examples, start a GPU worker, install
an adapter, or activate an expert without the exact authority required for that
boundary.

This plan is subordinate to `MASTER_PLAN.md`, `AGENTS.md`, the Core verification
contract, the signed Expert Fabric package lifecycle, and the owner resource
budget. Phase 21.7 remains independently open while local Phase 22 work proceeds.

## Research basis and sample policy

LoRA freezes the base model and trains low-rank adapter matrices. QLoRA keeps the
base frozen in 4-bit form and combines NF4, double quantization, and LoRA so that
adapter training has a bounded memory footprint. The first implementation uses
the documented Transformers, TRL, PEFT, and bitsandbytes path rather than a
private training algorithm:

- load the approved base with 4-bit NF4 and double quantization;
- use BF16 compute only when the admitted GPU reports support, otherwise FP16;
- call `prepare_model_for_kbit_training` before attaching LoRA;
- target all linear modules for QLoRA unless a versioned model-family policy
  explicitly narrows them;
- train conversational prompt/completion records with assistant-only or
  completion-only loss so prompts are not learning targets;
- pin the base revision, tokenizer revision, chat template, dependencies,
  container or environment manifest, seeds, and every training parameter.

There is no universal best number of examples. Published evidence ranges from
1,000 carefully curated instruction examples in LIMA to roughly 10,000 filtered
OpenAssistant examples in the original QLoRA/Guanaco path. FAM therefore uses an
empirical learning curve rather than a count-based success claim.

The primary sources checked for this implementation are:

- [LoRA](https://arxiv.org/abs/2106.09685), which establishes frozen base
  weights plus learned low-rank update matrices;
- [QLoRA](https://arxiv.org/abs/2305.14314), which establishes gradient flow
  through a frozen 4-bit base into LoRA adapters and the NF4, double-quantization,
  and paged-optimizer memory techniques;
- [LIMA](https://arxiv.org/abs/2305.11206), whose 1,000-example result is evidence
  for curation quality, not a universal minimum;
- the official [PEFT quantization guide](https://huggingface.co/docs/peft/developer_guides/quantization),
  which requires preparing the quantized model for training and documents
  `all-linear` targeting for QLoRA across model architectures; and
- the official [TRL SFT trainer guide](https://huggingface.co/docs/trl/en/sft_trainer),
  which documents assistant-only and completion-only loss controls.

These sources justify the backend mechanics, but none defines a generally valid
sample count for a new local capability. The owner-visible learning curve and
held-out promotion gate remain authoritative.

The default checkpoints are 256, 512, 1,000, 2,500, 5,000, and 10,000 unique,
approved training examples. Counts below 1,000 are development candidates unless
the capability policy explicitly defines a finite or exhaustive input space.
Validation and held-out sets are fixed before synthesis and never reduced to
increase the training count. Promotion requires a confidence-bounded held-out
improvement over the currently active package, no policy regression, and an
improvement that has not saturated at an earlier checkpoint. More examples do
not override bad provenance or a failed evaluation.

### Physical learning-curve record

Physical checkpoints are immutable experiments, not mutable releases. A failed
gate creates a signed non-promotable decision and cannot be converted. Aggregate
metrics may select the next predeclared mixture; held-out prompts, model outputs,
and per-case content remain unavailable to dataset authors.

| Plan | Fixed-suite status | Train mix Q/S/P/U | Aggregate result |
|---|---|---:|---|
| `quality256` | diagnostic predecessor | 256/16/16/16 | exposed the need for typed held-out semantics; not release-comparable |
| `balanced512` | predecessor suite | 256/96/96/64 | quality passed, policy failed; informed a broader policy set |
| `balanced1000` | suite `21773b83…d2684` | 400/120/360/120 | 51.39% quality, 1 safety failure, 0 policy failures; denied |
| `balanced2500` | suite `21773b83…d2684` | 1250/375/500/375 | 100% quality, 1 safety failure, 1 policy failure; denied |
| `balanced5000` | suite `21773b83…d2684` | 2500/1000/1000/500 | 100% quality, 1 safety failure, 3 policy failures; denied |
| `diverse2500` | suite `21773b83…d2684` | 1250/500/500/250 | 100% quality, 1 safety failure, 3 policy failures, 33.3% unrelated pass; denied |

The 256 and 512 results used predecessor evaluator semantics and are retained as
diagnostic history, not silently normalized into the fixed-suite series. The
1,000 through diverse-2,500 runs share the same sealed suite and held-out floor.
The 5,000 and diverse-2,500 results show that neither repetition nor prompt
diversity corrects the remaining failures by itself; a 10,000 run is not
justified.

A non-held-out development probe then separated the residual behavior: five
independent safety prompts were refused safely, one of five evidence-honesty
prompts invented a successful deployment, and exact arithmetic answers included
unrequested prose. Source inspection found that all adapters in this first
series trained raw string prompt/completion records while evaluation rendered
Qwen chat messages with thinking disabled. ADR 0141 starts a new worker-bound
series that trains conversational prompt/completion records with the same
`enable_thinking=false` template and `<|im_end|>` EOS used during evaluation.
The first run repeats `diverse2500` against the unchanged suite to isolate the
representation correction. No result changes the zero-failure safety and policy
gates.

## Non-negotiable boundaries

1. **Discovery is content-free and proposal-only.** Repeated failures are
   clustered from signed verifier identities, failed requirement identities,
   evidence digests, expert identity, and outcome metadata. Discovery never
   grants training authority.
2. **Existing terminal learning remains redacted.** Phase 20 intentionally
   removes prompts, candidates, verifier feedback, and application content at
   terminal commit. Phase 22 must not weaken or reverse that privacy decision.
3. **Training content requires a separate opt-in capture.** An owner-approved
   capture grant names capability, source kinds, workspace scopes, sensitivity,
   retention limit, and expiry. Only content copied while that grant is valid
   may enter a staging dataset.
4. **Split before synthesis.** Source families and failure clusters are assigned
   to train, validation, or held-out partitions before a teacher sees them.
   Synthetic descendants inherit the source partition. Held-out prompts,
   answers, verifier fixtures, and feedback are never disclosed to a teacher or
   training worker.
5. **Teacher output is untrusted.** Laguna, Gemma, or another approved teacher may
   propose examples. Deterministic verification or explicit human acceptance is
   required per example before sealing a dataset.
6. **Training is isolated and bounded.** A separate worker environment receives
   only the sealed training and validation partitions, an approved base model,
   and an effective resource budget. It receives no FAM database, home directory,
   network authority, held-out content, signing key, or install authority.
7. **Evaluation and activation are separate.** The training backend can produce
   an adapter artifact but cannot evaluate its own release claim, sign a package,
   install it, or make it routable.

## Production component map

| Component | Responsibility | Explicitly cannot do |
|---|---|---|
| `FailureDiscoveryService` | Convert pre-redaction verifier failures into content-free traces and proposals | Capture content or authorize training |
| `TrainingCaptureService` | Enforce owner grants and stage bounded source material | Generate examples after grant expiry |
| `DatasetFactory` | Assign source groups, generate candidates, verify, deduplicate, and seal partitions | Move descendants between partitions |
| `FactoryApprovalService` | Bind capability, data, base revision, license, budget, runtime, and expected outputs | Treat a resource budget as authority |
| `TrainingBackend` | Validate a sealed job and produce adapter plus metrics | Read held-out data, sign, install, or activate |
| `NvidiaQloraBackend` | Run the approved TRL/PEFT/bitsandbytes recipe in an isolated worker | Fall back silently to full fine-tuning or CPU |
| `FactoryResourceAdmission` | Check thermal, disk, RAM, VRAM, foreground pressure, conflicts, and cgroup limits | Override owner approval |
| `SpecialistEvaluator` | Compare candidate and incumbent on quality, safety, policy, latency, RAM, VRAM, and energy | Modify training data after seeing held-out results |
| `FactoryReleaseService` | Convert with pinned tooling, sign, install disabled, and create a canary | Bypass Expert Fabric package verification |
| `FactoryLifecycleService` | Promote, roll back, disable, retire, and expose receipts | Delete lineage or historical audit evidence |

The production composition adds one bounded `factory` unit. The unit supervises
discovery, dataset metadata, approvals, and worker lifecycle. GPU training is a
child worker, not an in-process Core operation.

## Durable contract and storage plan

Every mutable operation is owner-bound, encrypted at rest, revisioned, and emits
an append-only receipt. Large approved content is stored as encrypted immutable
blobs addressed by SHA-256; SQLite stores identities, lineage, state, grants, and
digests rather than duplicate plaintext.

The required records are:

- `FailureTrace` and `FailureTraceCluster`;
- `MissingCapabilityProposal`;
- `TrainingCaptureGrant` and capture receipt;
- `DatasetSource`, `DatasetExample`, `DatasetPartition`, and `SealedDataset`;
- leakage and deduplication report;
- `FactoryApproval` binding all six approval dimensions;
- `TrainingJob`, backend environment manifest, checkpoints, and terminal receipt;
- evaluation suite, measurements, regression decision, and held-out access log;
- conversion manifest, signed specialist package, canary decision, activation,
  rollback, retirement, and removal receipts.

State transitions use compare-and-swap revisions. Restart reconciliation may
resume idempotent inspection or evaluation, but it never replays capture,
training, installation, activation, or retirement authority.

## Dataset construction and leakage controls

1. Record a content-free, independently verified failure trace before normal
   terminal redaction.
2. Cluster by capability, failed requirement, verifier contract, and semantic
   failure family. A minimum count produces a proposal only.
3. Obtain an explicit capture grant. Copy only approved source fragments into an
   expiring staging area and record origin digest, source license, sensitivity,
   verifier, and grant revision.
4. Derive a stable source-family identifier. Assign the family to a partition
   with a deterministic seeded policy before teacher generation.
5. Ask an approved teacher only for descendants of training or validation source
   families. Never include held-out fixtures, expected answers, or feedback.
6. Verify every proposed answer. Rejected examples remain audit metadata but do
   not enter a sealed partition.
7. Normalize and exact-deduplicate content; use MinHash-style near-duplicate
   screening; for code, also compare normalized syntax and test-fixture lineage.
8. Reject cross-partition exact matches, near matches above the policy threshold,
   shared source families, and descendants whose provenance chain is incomplete.
9. Seal canonical JSONL partitions, manifests, counts, Merkle or ordered digest,
   tokenizer estimate, license set, sensitivity set, and tool versions.
10. Make the held-out decryption capability available only to the evaluator after
    the training artifact is terminal and immutable.

## Approval contract

One approval binds:

- target capability and acceptance policy;
- exact sealed dataset and allowed sensitivity;
- base model repository, immutable revision, tokenizer, and license;
- LoRA/QLoRA recipe and maximum trainable parameters;
- maximum wall time, steps, epochs, checkpoint bytes, and output bytes;
- RAM, VRAM, CPU, GPU, disk, thermal, energy, and foreground-pressure limits;
- backend environment digest and whether network access is prohibited;
- expiration and one terminal execution identity.

Changing any bound field creates a new approval. A discovery proposal, dataset
grant, model download, resource limit, or previous approval is not reusable
training authority.

## NVIDIA QLoRA backend

The initial student is the official Apache-2.0 Qwen3-1.7B model at an immutable
approved revision. The backend interface is model-family-neutral, but the first
qualified implementation is NVIDIA CUDA because the reference workstation has
an RTX 5080. Admission must probe the installed PyTorch/CUDA/bitsandbytes tuple;
current bitsandbytes wheels require a CUDA build containing the Blackwell target,
so the factory fails closed instead of accepting a generic version range.

The worker performs, in order:

1. verify environment, model, tokenizer, dataset, and approval digests;
2. reserve cgroup, GPU, disk, and energy budgets;
3. load the frozen 4-bit base and attach only the approved LoRA parameters;
4. train with deterministic seeds, bounded steps, checkpoint count, and output;
5. record loss, gradient, throughput, memory, VRAM, temperature, power, and
   interruption metrics at bounded intervals;
6. stop safely on revoked authority, thermal limit, pressure, disk reserve,
   non-finite loss, unexpected trainable parameters, or environment drift;
7. write the adapter and terminal receipt to a staging output directory;
8. release resources without marking the adapter accepted.

No automatic fallback to a different precision, model, device, dataset,
hyperparameter, or dependency version is allowed.

## Evaluation, release, and lifecycle

Evaluation runs both candidate and incumbent through the same immutable suite.
It reports per-requirement accuracy and confidence, refusal and policy behavior,
unrelated-capability regression, calibration, latency distributions, peak RAM and
VRAM, energy, artifact size, cold start, and scheduler compatibility. Promotion
requires all hard policy gates and the capability-specific minimum improvement.

An accepted adapter is converted only by digest-pinned tooling. The release
manifest binds base model revision, adapter digest, merge policy, quantization,
tokenizer, chat template, capability declaration, hardware envelope, dataset and
evaluation lineage, and conversion environment. The package is signed by the
existing release boundary, installed disabled, and exposed to a bounded canary.
Only a separate activation decision may make it selectable.

Canary regression disables the candidate and restores the known-good expert.
Retirement removes routability and optional artifact bytes but preserves dataset
digests, approvals, job/evaluation/release receipts, package identity, and the
reason for retirement.

## Step-by-step delivery and evidence

### 22.1 Discovery and provenance-bound generation

- Replace the minimal discovery shape with strict content-free production
  contracts and deterministic cluster identities.
- Capture failures at the verifier/terminal boundary before content redaction.
- Add owner-private persistence, supervised proposal generation, Console/Shell
  visibility, and a synthetic-example proposal path that requires a capture
  grant and per-example verification.
- Prove terminal redaction is unchanged and discovery cannot start training.

### 22.2 Approval

- Add the six-dimension approval contract, confirmed Shell/Console controls,
  expiration, revocation, revision binding, and one-use execution identity.
- Prove every omitted, changed, stale, or revoked field denies before a worker is
  created.

### 22.3 Training backend

- Define `TrainingBackend`, environment probing, and terminal receipts.
- Build the isolated NVIDIA QLoRA worker and qualify Qwen3-1.7B on the reference
  RTX 5080 with a non-promotable smoke dataset before using approved real data.
- Record exact dependency and CUDA compatibility evidence.

### 22.4 Immutable datasets

- Complete encrypted blob storage, canonical manifests, split-before-synthesis,
  exact and near deduplication, leakage checks, license checks, and held-out key
  isolation.
- Run learning-curve checkpoints rather than selecting a count by intuition.

### 22.5 Safe scheduling

- Bind the effective hardware profile and worker cgroup policy.
- Deny on inference conflicts, foreground pressure, thermal headroom, insufficient
  disk reserve, RAM/VRAM limit, power policy, or revoked approval.
- Prove safe checkpoint-and-stop behavior for signals and service restart.

### 22.6 Evaluation

- Evaluate candidate versus incumbent across quality, safety, policy, unrelated
  regressions, latency, RAM, VRAM, energy, package size, and scheduler behavior.
- Keep held-out content inaccessible to teachers and training workers and emit a
  signed comparison decision.

### 22.7 Conversion and canary

- Pin and verify conversion tools, create the signed Expert Fabric package,
  install disabled, run a canary, and activate only after the separate gate.
- Prove the scheduler selects the specialist only for its declared capability.

### 22.8 Rollback and retirement

- Detect canary or production regression, atomically restore known-good routing,
  support confirmed manual rollback and retirement, and preserve all audit
  identities after optional artifact deletion.

## Phase exit evidence

The Phase 22 exit artifact must be produced from the signed installed product and
must contain:

- the verified local failure cluster and proposal;
- explicit capture and training approvals;
- sealed split manifests and leakage report;
- actual QLoRA worker environment, resource, and terminal receipts;
- candidate/incumbent held-out and hardware comparison;
- signed installed package and scheduler selection evidence;
- forced regression rollback, manual retirement, optional artifact removal, and
  retained audit query;
- proof that raw prompts and held-out content are absent from discovery, receipts,
  logs, and unrelated product storage.

Passing unit tests, the Phase 13 classifier, an in-process mock backend, a toy
dataset, same-model self-evaluation, or an unsigned adapter does not satisfy the
exit gate.

## Completed physical exit

Phase 22 passed the production exit on 2026-07-18. The canonical physical run
`phase22-stable-toposort-diverse2500-chat-20260718-03` used the explicit Qwen
chat prompt/completion format with thinking disabled, verified 2,868 source
fixtures, trained 2,500 records in an offline QLoRA sandbox, and produced a
46,351,277-byte adapter with frozen base weights and no held-out access. Its
signed comparison was promotable: 100% quality, 94.93% lower confidence bound,
zero safety failures, zero policy failures, 83.33% unrelated quality, compatible
scheduler placement, and discarded held-out plaintext.

The final lifecycle was repeated from a fresh seven-component Ed25519-signed
FAM_OS installation. The installed product converted Qwen3-1.7B to a
2,165,039,328-byte Q8_0 base and the LoRA to a 34,892,384-byte F16 adapter,
created a signed specialist package disabled, proved exact
`code.generate.python` selection, passed the declared deterministic Python
canary, activated, manually rolled back, reactivated, retired, removed runtime
and artifact bytes, and retained audit history. The qualification installation
was diagnosed healthy and completely removed.

The authoritative content-free aggregate is
`artifacts/training/phase22-stable-toposort-diverse2500-chat-20260718-03/phase22-exit-evidence.json`.
It binds the sealed suite, signed comparison decision, training evidence,
release evidence, installed module digest, and signed release manifest. Raw
prompts, candidate outputs, held-out cases, and the ephemeral qualification key
are absent.
