# Expert residency lifecycle

## Purpose

`fam.scheduler.expert-residency/v1alpha1` is the durable scheduler truth for
whether a package-bound runtime artifact is absent, retained, leased by requests,
or being removed. Package installation and enablement do not imply residency.

## States

| State | Required evidence | New lease allowed |
|---|---|---:|
| `cold` | Provider-confirmed artifact absence, no leases or loaded measurements | No |
| `warm` | Provider-confirmed loaded artifact, no active leases | Yes |
| `active` | Provider-confirmed loaded artifact and at least one unexpired lease | Yes |
| `evicting` | Previously warm artifact, exact eviction ID, no leases | No |

`initial_cold_residency_catalog` may be called only after the caller confirms
provider absence. It is named accordingly so startup cannot silently equate an
empty state file with a cold runtime. If a provider may already contain models,
startup must observe it and initialize/reconcile against those observations.

Each record binds one expert ID to one runtime artifact ID, has a monotonic
record revision, and retains the latest provider measurements and transition
reason. The catalog has its own monotonic revision and compare-and-swap boundary.

## Leases

A request lease has unique lease/request IDs plus acquisition and expiration
times. Acquiring the first lease moves warm to active. Additional leases retain
active. Releasing or expiring the final lease returns the expert to warm. Cold
and evicting states reject new leases. Duplicate lease or request ownership and
backward transition time fail closed.

Expired leases do not grant permanent residency after a crashed request. Explicit
expiration is revision-bound and durable.

## Reconciliation

Provider-loaded observations move cold to warm and refresh loaded RAM, accelerator
bytes, and context tokens. Provider absence moves warm to cold and completes a
crash-interrupted evicting transition. An active expert disappearing is a hard
conflict: FAM preserves the durable active record rather than hiding an in-flight
request failure as a clean cold transition.

Unknown provider models are ignored; this catalog owns only explicitly bound FAM
expert/artifact identities. Duplicate provider identities fail.

## Eviction barrier

Eviction persists `evicting` before calling the runtime. Ollama's unload adapter
already polls `/api/ps` until absence, so only then can the coordinator persist
`cold`.

If unload fails, the coordinator re-observes:

- confirmed present restores `warm` and rethrows the failure;
- confirmed absent completes `cold` despite a late/failed unload response;
- observation failure leaves durable `evicting` for later reconciliation.

This avoids both false release and false residency after ambiguous provider
failures.

## Persistence

`JsonExpertResidencyRepository` stores one strict private JSON document. An
adjacent private lock serializes cross-process initialize/read/CAS operations.
Writes use a mode-0600 temporary file, `fsync`, atomic replace, and directory
`fsync`. Relative paths, symlink state/locks, nonregular locks, broad permissions,
catalog identity changes, stale revisions, and skipped revisions are rejected.

## Canonical evidence

`artifacts/scheduler/phase7.3/qwen-residency-lifecycle-canonical/` uses an
isolated full-reference Ollama service and the already downloaded Qwen expert.
It preserves strict snapshots of:

```text
cold -> warm -> active -> warm -> evicting -> cold
  0       1        2        3          4        5
```

The final transition follows confirmed `/api/ps` absence. The private durable
file is revision 5, service CPU/RAM evidence is retained, and the transient
service ends inactive. The earlier sibling run remains historical diagnostic
evidence and is not the canonical final implementation capture.
