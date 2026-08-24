# Final Master Plan audit

## Current conclusion

FAM_OS is integration incomplete. The historical component and installed gates
through Phase 20, installed trusted-fabric steps 21.1–21.6, the real Expert
Factory in Phase 22, and clean built-artifact qualification steps 23.1–23.2 are
complete. Phase 23.4 and 23.6 now pass. Phase 21.7, the physical-remote portion
of 23.3, and Phase 23.5, 23.7, and 23.8 remain open or in progress. No earlier statement that
the whole Master Plan had no unchecked items is current evidence.

The authoritative machine-readable status is
`configs/integration/coverage.json`. This document summarizes the human audit;
it does not upgrade maturity by itself.

## Current verified baseline

- One built wheel passed all 1,257 standard tests independently in Base,
  Verification, Mathematics, Media, Hardware, Training, and VS Code profiles.
- The Hardware profile additionally discovered all 11 explicitly opt-in live
  smoke cases; the clean profile records them as skips and does not claim the
  separate physical gate.
- Repository-wide Ruff passes.
- All 286 generated Draft 2020-12 schema artifacts validate.
- Signed installed evidence exists for the unified Core, application weaving,
  declared verifiers, memory/adaptation lifecycle, same-host trusted-device
  flows, and the governed QLoRA specialist lifecycle.
- Signed installed release `fam-os-query-bound-20260718-02` additionally proves
  query-bound extractive identity grounding and fail-closed rejection of an
  unrelated FAM_OS residency-readiness prompt.
- The normal owner service loads from the installed active tree, is configured
  to restart on failure, and serves Console on loopback port 8765.
- Signed seven-component matrix `phase23-installed-20260718-11` passes all seven
  installed scenario groups: local, application including outbound and inbound
  MCP, memory/restart, bounded Laguna/Gemma escalation, media, same-host remote,
  and Factory. It also proves restart while awaiting approval, uncertain-action
  recovery, recovery-mode Console truth, owner-service preservation, complete
  candidate removal, candidate-only fault injection, and a Factory lifecycle
  with no Phase 22 acceptance-composition import. Its same-host remote result is
  not physical Phase 21.7 evidence.
- Signed installed hardware matrix `phase23-hardware-20260718-06` passes the
  independent 16 GiB CPU-only and full RTX workstation profiles, grounded
  memory across restart, isolated Laguna/Gemma probes, and independent
  Console-to-host/provider/cgroup authority comparisons.

These facts are subsystem evidence. They do not satisfy the final cross-profile,
cross-host, soak, human-review, or fresh-user release-candidate gates.

## Open requirements

1. Phase 21.7 requires one additional physical Linux host and a cross-host
   success/disconnect/recovery artifact. Two prefixes on one machine do not
   count.
2. Phase 23.3 has one passing installed matrix covering local, application,
   MCP, memory, Laguna/Gemma escalation, media, same-host remote, and Factory,
   including restart while awaiting approval and uncertain-action recovery. It
   remains in progress until the remote case is repeated across two physical
   Linux hosts under Phase 21.7.
3. Phase 23.5 requires at least 24 hours of the installed release under
   inference, connector churn, memory/GPU/low-disk pressure, verifier/Ollama
   crashes, daemon restart, and update rollback.
4. Phase 23.7 requires an independent human security review with no unresolved
   high or critical finding. Automated audits are supporting evidence only.
5. Phase 23.8 requires a signed fresh-user install, update, rollback, recovery,
   and total-removal matrix using the final release candidate and trust key.

## Audit rules

- Source tests do not substitute for installed evidence.
- A generated artifact is evidence only when its producer, input identity,
  release identity, and validation contract are current and reproducible.
- Acceptance-only harnesses cannot satisfy installed-product requirements.
- Same-host peer tests cannot satisfy the physical-device gate.
- A short soak cannot be extrapolated to 24 hours.
- Human review cannot be self-certified by the implementation agent.
- The program status remains `integration_incomplete` until every requirement
  above has direct current evidence.

## Latest correction

The Phase 23 audit found that exact citation provenance did not imply relevance
to the current query. ADR 0150 and handoff 0174 bind current retrieval
declarations to the exact query and require exact source/cited-span coverage.
Legacy query-unbound declarations remain readable but cannot newly verify.

The same audit refreshed the stale integration coverage and final-integration
documents: Scheduler policy/residency and the installed Expert Factory are no
longer described as unimplemented, while their remaining Phase 23 matrices stay
explicitly open.

The next audit built the shipped wheel and found its production verifier and
runtime-catalog configuration missing. ADR 0151 and handoff 0176 package exact
canonical copies with signed/source precedence and add a split clean-profile
runner. Consolidated artifact `phase23-required-20260718-01` proves 23.1 and
23.2 against one wheel digest. It does not promote opt-in hardware skips into
physical execution and does not satisfy any installed-release gate after 23.2.

The Phase 23.3 call-path audit then found that restart-safe action policy had no
production caller after the unified Core replacement. ADR 0152 and handoff 0177
wire cross-repository recovery before any client server starts, discard prior
approval, require exact durable fresh reapproval, reconstruct independently
observable directory outcomes without provider retry, and block inconclusive
actions. The corrected tree passes all 1,263 source tests with two declared
environment skips. This repairs a Phase 17.4 production reachability defect,
but remains source evidence until the same fault windows pass from the single
installed Phase 23.3 release candidate.

Signed installed matrix `phase23-installed-20260718-08` subsequently passed
those fault windows together with local, MCP, memory, escalation, media,
same-host remote, and Factory scenarios. The matrix advances 23.3 but cannot
replace its physical-remote dependency. The hardware-profile audit also found
that the named profiles were benchmark configuration only and were not applied
to the installed managed Ollama service. The product now loads canonical
packaged validation profiles, applies their cgroup and accelerator policies,
reports their effective capacity through Console, and has a dedicated signed
installed dual-profile matrix. A first matrix attempt remains failed evidence:
it exposed query-incomplete grounded synthesis, stale Console policy-field
collection, orphaned managed-service cleanup, and owner-GPU contention. Those
implementation and harness defects were corrected before the fresh rerun.

Fresh matrix `phase23-installed-20260718-11` supersedes that scenario evidence.
It removes checkout source from both mutation fault injection and Factory
composition, validates candidate identity before mutation, records no imported
Phase 22 acceptance composition, and adds a missing-key recovery Console proof.
All seven scenario groups, complete removal, and owner-service preservation
pass. The same-host remote limitation keeps only the physical portion of 23.3
open.

Fresh hardware matrix `phase23-hardware-20260718-06` passes both named installed
profiles and completes 23.4. Its Console values for CPU, schedulable RAM, VRAM,
storage, policy, signed catalog, and residency agree with independent host,
cgroup, filesystem, NVIDIA, and Ollama observations. Together with Run 11's
durable terminal, permissions, action-audit, document-index, restart, and
missing-key transitions, this completes 23.6.

The first 24-hour soak attempt is retained as failed evidence. It exposed that
the installed verifier could not create Bubblewrap namespaces from a truly
unconfined, `NoNewPrivileges` user service on this host's restricted AppArmor
policy. ADR 0155 adds a signed dedicated profile and applies it only to a
manager-created transient verifier service. The source and mechanics probes
pass, but the dedicated profile still requires an explicit administrator load
before the 24-hour clock can restart.

The Phase 23.8 audit also found that the public removal command deleted only the
signed prefix. ADR 0156 adds owner-bound state/runtime markers, confirmed
complete removal, connector identity hardening, and a separate installed
lifecycle runner. This corrects source readiness but does not complete 23.8;
the runner must pass against the final post-soak signed candidate.

The first lifecycle preflight exposed another false-health path: diagnosis
derived its managed files by globbing what remained, so deleting a launcher
also deleted it from the expected set. ADR 0157 replaces that behavior with a
versioned safe-path and SHA-256 ledger covering generated launchers, units, and
retained trust keys. Qualification imports were also normalized under the
`tools.*` package so unittest discovery and module execution see the same code.
The fourth preflight passes install, update, rollback, damage diagnosis, repair,
connector installation, service HTTP 200, and total removal; only the unloaded
required AppArmor sandbox profile fails. The complete source suite now passes
1,350 tests with two declared skips. Phase 23.8 remains open until the exact
post-soak candidate passes every event.

Installed owner testing then exposed a Phase 19 usability and truthfulness gap:
Console could select connected applications but not an ordinary local folder,
and a model could print an `ls` command despite no machine action. ADR 0161 and
handoff 0184 add explicit owner-local workspace selection, bounded directory
and file observations, receipt-backed tool activity, approval-relative folder
creation, and deterministic exact folder-list results. Signed release
`fam-os-workspace-20260718-02` is healthy and passed the live selected-folder
probe. This completes corrective step 19.12 but opens 19.13 explicitly for a
bounded multi-step repository tool loop; it does not change the remaining
physical-host, soak, human-review, or final lifecycle gates.

The continuing signed-catalog audit also found ambiguous duplicate archive
members and verifier-superset acceptance. ADR 0160 and handoff 0183 require
canonical unique expert archive members and exact signed verifier equality.
Those corrections are included in the same installed release, but separate
archive readers remain subject to the continuing whole-plan audit.
