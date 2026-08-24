(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.FamTaskUpdates = api;
}(typeof globalThis === "undefined" ? this : globalThis, function () {
  const stateOrder = Object.freeze({
    accepted: 0,
    running: 1,
    waiting_approval: 2,
    cancelling: 3,
    terminal: 4,
  });

  function accepts(current, next) {
    if (!next || typeof next !== "object") return false;
    if (!current) return true;
    if (next.session_id !== current.session_id) return false;
    if (current.state === "terminal") return next.state === "terminal";
    if (next.revision < current.revision) return false;
    if (next.revision > current.revision) return true;
    return (stateOrder[next.state] ?? -1) >= (stateOrder[current.state] ?? -1);
  }

  function resultPresentation(result) {
    const kind = result?.result_kind || "conversation_answer";
    const labels = {
      conversation_answer: "MODEL ANSWER · NO MACHINE ACTION",
      grounded_answer: "GROUNDED ANSWER",
      action_proposal: "ACTION NOT EXECUTED",
      action_receipt: "VERIFIED ACTION RECEIPT",
      capability_unavailable: "CAPABILITY UNAVAILABLE · NO ACTION ATTEMPTED",
      changeset_proposal: "ENGINEERING CHANGESET PROPOSED · NOT EXECUTED",
      verified_changeset_receipt: "VERIFIED ENGINEERING CHANGESET RECEIPT",
      publication_proposal: "PUBLICATION PROPOSED · NOT PUBLISHED",
      publication_receipt: "VERIFIED PUBLICATION RECEIPT",
      engineering_capability_unavailable: "ENGINEERING CAPABILITY UNAVAILABLE · NO EFFECT",
      engineering_execution: (
        result?.assurance === "verified"
          ? "VERIFIED ENGINEERING EXECUTION"
          : result?.assurance === "verification_waived"
            ? "ENGINEERING EXECUTED · VERIFICATION WAIVED"
            : "ENGINEERING EXECUTED · UNVERIFIED"
      ),
    };
    return {
      label: labels[kind] || "RESULT TYPE UNKNOWN",
      canReverse: (
        (kind === "action_receipt" || kind === "verified_changeset_receipt")
        && result?.verified === true
      ),
      evidenceLabel: (
        kind === "action_receipt"
          ? `${(result.evidence_ids || []).length} verified action evidence record${(result.evidence_ids || []).length === 1 ? "" : "s"}`
          : kind === "verified_changeset_receipt"
            ? `${(result.evidence_ids || []).length} verified engineering evidence record${(result.evidence_ids || []).length === 1 ? "" : "s"}`
          : kind === "publication_receipt"
            ? `${(result.evidence_ids || []).length} verified publication evidence record${(result.evidence_ids || []).length === 1 ? "" : "s"}`
          : kind === "engineering_execution"
            ? `${(result.evidence_ids || []).length} engineering effect evidence record${(result.evidence_ids || []).length === 1 ? "" : "s"}`
          : kind === "grounded_answer"
            ? `${(result.evidence_ids || []).length} grounding evidence record${(result.evidence_ids || []).length === 1 ? "" : "s"}`
            : "No action receipt"
      ),
    };
  }

  function displayStepState(taskState, stepState) {
    if (taskState === "terminal" && stepState === "pending") return "not_taken";
    return stepState;
  }

  return Object.freeze({accepts, resultPresentation, displayStepState});
}));
