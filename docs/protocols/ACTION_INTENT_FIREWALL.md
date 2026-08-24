# Action Intent Firewall Protocol

## Boundary

Action intent is an authority request, not a model-routing hint. The firewall
runs before grounding, model selection, memory prompt assembly, and inference.
It receives the current natural-language command and a bounded local session
identity; it never receives or trusts model output.

## Outcomes

Every request takes exactly one ingress outcome:

1. Non-action language continues to the normal answer lifecycle.
2. A recognized action with missing parameters returns `action_proposal` and
   records only the bounded expiring parameter state needed for a follow-up.
3. A recognized action with parameters resolves to one live action capability
   and enters the Application Fabric lifecycle.
4. An action without a matching live capability returns
   `capability_unavailable`; no model or provider is called.

The current pending state is process-local, capped at 128 sessions, and expires
after 15 minutes. Cancellation removes it. It grants no capability and survives
neither process restart nor identity change.

## Result taxonomy

- `conversation_answer`: model-generated content with no claim of machine work.
- `grounded_answer`: answer content supported by authorized observation evidence.
- `action_proposal`: an action needs input, was denied, or did not execute.
- `action_receipt`: a confirmed action completed and independent postconditions
  passed. This kind requires verified status and evidence.
- `capability_unavailable`: no authorized action route existed and no action was
  attempted.

Inference candidates can become conversation or grounded answers. They can
never become action receipts. Application actions use deterministic parameters
or a capability-specific candidate only to prepare a proposal; after successful
execution Core replaces that candidate with a fixed receipt derived from the
verified action record. Final assembly independently requires every execute step
to have exactly one successful bound action-result reference and same-grant
audit evidence. A passing verifier attached only to model prose is insufficient;
the release is rejected and the prose is never exposed as a receipt.

## Owner directory capability

`os.directory.create` is scoped to the discovered owner home root. The preview
contains the exact target and mode `0700`. Approval is always required. Parent
directories are opened descriptor-by-descriptor with `O_DIRECTORY` and
`O_NOFOLLOW`; traversal outside the root and symlink traversal are rejected.

The trusted postcondition observes that the target exists and is empty. The
reversal token contains only the created device/inode identity. Reversal uses
`os.directory.remove-empty`, requires a new preview and approval, and succeeds
only when the same inode remains an empty directory. Nonempty, replaced, moved,
or symlinked targets are not removed.

Application audit records contain a SHA-256 of the resource URI, not the raw
path, prompt, preview, parameters, provider output, or reversal token.

## Presentation

Shell prints the result kind. Console labels model answers as having no machine
action, labels unavailable/proposal outcomes as not executed, and reserves
“verified action receipt” for verified action results. Terminal alternatives
that were never traversed are displayed as `not taken`, not as indefinitely
pending work.

## Compatibility

The typed result roots are `fam.core.task-result/v1alpha2` and
`fam.shell.snapshot/v1alpha2`. Frozen `v1alpha1` roots remain registered for
exact decoding. Migration is explicit and conservative: legacy results become
conversation answers because old documents cannot prove action semantics.
