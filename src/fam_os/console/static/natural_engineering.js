"use strict";

const FamNaturalEngineering = (() => {
  const prefix = "/api/v1/engineering/natural-language/proposals";
  let api = null;
  let hooks = null;
  let current = null;
  let restoredWorkspace = null;
  let liveTimer = null;

  const byId = id => document.getElementById(id);

  function configure(request, options) {
    api = request;
    hooks = options;
  }

  function active() {
    return ["resources", "grant", "review", "changeset", "publication", "rollback"].includes(current?.phase);
  }

  function running() {
    return current?.phase === "running";
  }

  async function start(prompt, scope, workspaceRoot, authorityProfile = "workspace") {
    current = null;
    const proposal = await api(prefix, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        prompt, workspace_root: workspaceRoot,
        authority_profile: authorityProfile,
      }),
    });
    const turn = hooks.startTurn(prompt, scope, proposal.proposal_id);
    current = {
      proposal, turn, phase: "grant", changesetId: null,
      rollbackRequired: false, workspaceRoot,
    };
    if (authorityProfile === "ask") {
      await activate();
    } else {
      renderProposal();
    }
    hooks.setBusy(false);
  }

  async function restore(workspaceRoot, scope) {
    if (!workspaceRoot || restoredWorkspace === workspaceRoot) return;
    const thread = await api(
      `${prefix}/thread?workspace_root=${encodeURIComponent(workspaceRoot)}`,
    );
    restoredWorkspace = workspaceRoot;
    hooks.resetTranscript();
    const turns = thread.turns || [];
    for (const saved of turns) {
      const turn = hooks.startTurn(
        saved.objective,
        `${profileLabel(saved.authority_profile)} · ${scope}`,
        saved.turn_id,
      );
      current = {turn, phase: null, proposal: null};
      const failed = saved.status === "failed";
      const running = saved.status === "running";
      renderText(
        saved.final_response || saved.failure || (running
          ? "This turn was interrupted before it produced a final response."
          : "This turn did not retain a final response."),
        failed ? "Agent turn failed" : running ? "Agent turn interrupted" : "Completed agent turn",
        `${saved.events?.length || 0} durable tool event(s)`,
      );
    }
    if (turns.length) renderAgentEvents(turns[turns.length - 1].events || []);
    current = null;
  }

  function profileLabel(profile) {
    return {ask: "Ask", workspace: "Workspace", full_os: "Full OS"}[profile]
      || profile || "Agent";
  }

  function renderAgentEvents(events) {
    const calls = new Map();
    for (const event of events) {
      if (event.event_kind === "call") calls.set(event.call_id, event);
    }
    const rows = events.filter(event => event.event_kind === "result").map(event => {
      const call = calls.get(event.call_id);
      const item = document.createElement("li");
      item.dataset.status = event.payload.succeeded ? "succeeded" : "failed";
      const head = document.createElement("header");
      const label = document.createElement("strong");
      label.textContent = event.tool_id.replaceAll("_", " ");
      const status = document.createElement("span");
      status.textContent = event.payload.succeeded ? "completed" : "failed";
      const output = document.createElement("pre");
      const reason = call?.payload?.reason ? `${call.payload.reason}\n` : "";
      output.textContent = limit(`${reason}${event.payload.output || ""}`, 6000);
      head.append(label, status);
      item.append(head, output);
      return item;
    });
    if (rows.length) byId("tool-activity").replaceChildren(...rows);
  }

  async function decide(approved) {
    if (!active()) return false;
    if (!approved) {
      if (current.phase === "publication") await declinePublication();
      withhold();
      return true;
    }
    hooks.setBusy(true);
    hideApproval();
    try {
      if (current.phase === "resources") await approveIntegrationResources();
      else if (current.phase === "grant") await activate();
      else if (current.phase === "review") await waiveReview();
      else if (current.phase === "changeset") await applyChangeset();
      else if (current.phase === "publication") await applyPublication();
      else await applyRollback();
    } finally {
      hooks.setBusy(false);
    }
    return true;
  }

  function renderProposal() {
    const grant = current.proposal.grant.payload;
    const authorities = grant.authorities.join(", ");
    const highRisk = current.proposal.separately_confirmed_authorities || [];
    const resource = current.proposal.integration_resource_grant;
    const resourceGrant = resource?.document?.payload;
    const resourceAuthorities = (resourceGrant?.authorities || [])
      .filter(value => value !== "execute");
    const blocked = highRisk.filter(value =>
      value !== "publish" && !resourceAuthorities.includes(value));
    renderSteps([
      ["succeeded", "Interpret natural-language request", "intent"],
      ["succeeded", "Inspect repository and calculate bounded authority", "observe"],
      [blocked.length ? "failed" : "waiting", "Authorize the exact engineering grant", "confirm"],
      ["waiting", "Create, verify, and preview candidate changes", "prepare action"],
    ]);
    if (blocked.length) {
      current.phase = null;
      renderText(
        `This request includes ${blocked.join(", ")}. Those powers require a separate owner ceremony and were not activated.`,
        "Separate authority required", "No effects executed",
      );
      hideApproval();
      return;
    }
    if (resource && resource.status !== "approved") {
      current.phase = "resources";
      const scope = resourceGrant.scope;
      const network = scope.network_hosts.length
        ? scope.network_hosts.join(", ") : "none";
      const secrets = scope.secret_refs.length
        ? scope.secret_refs.join(", ") : "none";
      renderSteps([
        ["succeeded", "Interpret exact integration resources", "proposal only"],
        ["waiting", "Approve network and opaque-secret scope", "separate owner ceremony"],
        ["waiting", "Authorize ordinary engineering task", "separate checkpoint"],
        ["waiting", "Create, verify, and preview candidate", "no effect yet"],
      ]);
      renderText(
        `FAM identified exact integration resources. Network destinations: ${network}. Opaque secret references: ${secrets}. Maximum network transfer: ${resourceGrant.resource_impact.max_network_bytes} bytes. Maximum ephemeral integration storage: ${resourceGrant.resource_impact.max_changed_bytes} bytes. PostgreSQL secrets use consumer integration:postgresql and tool key POSTGRES_PASSWORD. Secret values will not be shown to the model or stored in this proposal. Approval digest: ${resource.approval_sha256}`,
        "Integration resource approval required", "No process, network, secret, or repository effect executed",
      );
      showApproval(
        `Authorize ${resourceAuthorities.join(", ")} for this integration task`,
        `${scope.scope_id} · ${network} · secret refs ${secrets}`,
        "Authorize integration resources",
      );
      return;
    }
    current.phase = "grant";
    renderText(
      `FAM understood the request and prepared a bounded grant for ${authorities}. No repository change has been made.${highRisk.includes("publish") ? " Any later push or draft PR will require a second exact approval." : ""}`,
      "Grant approval required", "Proposal only",
    );
    showApproval(
      "Authorize this bounded engineering task",
      `${grant.scope.workspace_roots[0]} · ${authorities}`,
      "Authorize task",
    );
  }

  async function activate() {
    current.phase = "running";
    renderSteps([
      ["succeeded", "Authorize the selected agent profile", "owner grant"],
      ["running", "Model is inspecting and working with tools", "live local agent"],
      ["waiting", "Verify the requested outcome", "real command evidence"],
      ["waiting", "Present exact changes for approval", "owner checkpoint"],
    ]);
    showLiveControls();
    liveTimer = setInterval(() => refreshLive().catch(() => {}), 350);
    try {
      const result = await api(
        `${prefix}/${encodeURIComponent(current.proposal.proposal_id)}/activate`,
        {
          method: "POST", headers: {"Content-Type": "application/json"},
          body: JSON.stringify({confirmed: true}),
        },
      );
      await refreshLive().catch(() => {});
      renderOutcome(result.engineering_task);
    } finally {
      clearInterval(liveTimer);
      liveTimer = null;
      hideLiveControls();
    }
  }

  async function refreshLive() {
    if (!current?.workspaceRoot) return;
    const thread = await api(
      `${prefix}/thread?workspace_root=${encodeURIComponent(current.workspaceRoot)}`,
    );
    const turn = (thread.turns || []).at(-1);
    if (!turn) return;
    renderAgentEvents(turn.events || []);
    const results = (turn.events || []).filter(event => event.event_kind === "result");
    current.turn.answer.textContent = results.length
      ? `Working… ${results.length} tool result(s) observed. Latest: ${results.at(-1).tool_id.replaceAll("_", " ")}.`
      : "Starting the local model and preparing its tools…";
  }

  async function sendControl(kind, content) {
    if (!running() || !current.workspaceRoot) return false;
    const instruction = content.trim();
    if (!instruction) return false;
    await api(`${prefix}/thread/control`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        workspace_root: current.workspaceRoot, kind, content: instruction,
      }),
    });
    byId("agent-control-status").textContent = kind === "cancel"
      ? "Cancellation requested; the agent will stop before its next model step."
      : "Guidance queued for the agent's next model step.";
    return true;
  }

  async function steer() {
    const input = byId("agent-guidance");
    if (await sendControl("steer", input.value)) input.value = "";
  }

  async function cancel() {
    return sendControl("cancel", "Cancelled by the owner from the Console.");
  }

  function showLiveControls() {
    byId("agent-control").classList.remove("hidden");
    byId("cancel").classList.remove("hidden");
    byId("agent-control-status").textContent = "Tool results will appear here while the run is active.";
  }

  function hideLiveControls() {
    byId("agent-control").classList.add("hidden");
    byId("cancel").classList.add("hidden");
  }

  async function approveIntegrationResources() {
    const result = await api(
      `${prefix}/${encodeURIComponent(current.proposal.proposal_id)}/integration-resource-decision`,
      {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({confirmed: true}),
      },
    );
    current.proposal = result.proposal;
    renderProposal();
  }

  async function applyChangeset() {
    const result = await api(
      `${prefix}/${encodeURIComponent(current.proposal.proposal_id)}/changeset-decision`,
      {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          changeset_id: current.changesetId, confirmed: true,
        }),
      },
    );
    renderOutcome(result.engineering_task);
  }

  async function waiveReview() {
    const result = await api(
      `${prefix}/${encodeURIComponent(current.proposal.proposal_id)}/review-waiver`,
      {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          checkpoint_id: current.reviewWaiver.checkpoint_id,
          finding_id: current.reviewWaiver.finding_id,
          consequences_sha256: current.reviewWaiver.consequences_sha256,
          confirmed: true,
        }),
      },
    );
    renderOutcome(result.engineering_task);
  }

  async function applyRollback() {
    const result = await api(
      `${prefix}/${encodeURIComponent(current.proposal.proposal_id)}/rollback`,
      {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          rollback_id: current.rollbackId, confirmed: true,
        }),
      },
    );
    renderOutcome(result.engineering_task);
  }

  async function applyPublication() {
    const result = await api(
      `${prefix}/${encodeURIComponent(current.proposal.proposal_id)}/publication-decision`,
      {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          publication_proposal_id: current.publicationId, confirmed: true,
        }),
      },
    );
    renderOutcome(result.engineering_task);
  }

  async function declinePublication() {
    await api(
      `${prefix}/${encodeURIComponent(current.proposal.proposal_id)}/publication-decision`,
      {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          publication_proposal_id: current.publicationId, confirmed: false,
        }),
      },
    );
  }

  function renderOutcome(task) {
    if (task.outcome === "independent_review_blocked") {
      const waiver = task.review_waiver_checkpoint;
      current.phase = "review";
      current.reviewWaiver = waiver;
      renderSteps([
        ["succeeded", "Understand, inspect, generate, and verify candidate", "candidate"],
        ["failed", `${waiver.discipline} review finding: ${waiver.title}`, waiver.severity],
        ["waiting", "Resolve the finding or explicitly waive it", "owner decision"],
        ["waiting", "Approve the exact changeset", "with reduced assurance after waiver"],
      ]);
      renderText(
        `Independent ${waiver.discipline} review blocked this changeset${waiver.path ? ` at ${waiver.path}` : ""}. Waiving this exact finding does not claim it was resolved; the resulting assurance is ${waiver.truthful_assurance_after_waiver}. Consequences digest: ${waiver.consequences_sha256}`,
        "Independent review finding blocks apply",
        `${(task.reviews || []).length} durable review checkpoint(s)`,
      );
      showApproval(
        `Waive ${waiver.severity} ${waiver.discipline} finding`,
        `${waiver.checkpoint_id} · ${waiver.finding_id} · reduced assurance`,
        "Explicitly waive finding",
      );
      return;
    }
    if (task.outcome === "changeset_approval_required") {
      const changeset = task.changeset.payload;
      const diagnostics = task.runtime_diagnostics || [];
      const databases = task.database_engineering ? 1 : 0;
      const integrations = task.integration_environment ? 1 : 0;
      current.phase = "changeset";
      current.changesetId = changeset.changeset_id;
      renderSteps([
        ["succeeded", "Understand and inspect repository", "observe"],
        ["succeeded", "Generate changes in isolated candidate", "modify candidate"],
        ["succeeded", (diagnostics.length || databases || integrations)
          ? "Run signed verification, diagnostics, database, and integration lifecycle"
          : "Run signed candidate verification", "verify"],
        ["waiting", "Approve the exact changeset preview", "confirm action"],
        ["waiting", "Apply and reverify the owner workspace", "execute action"],
      ]);
      renderText(
        checkpointText(task), "Verified changeset ready",
        `${task.candidate_verifications.length} verifier, ${diagnostics.length} runtime diagnostic, ${databases} database, and ${integrations} cleaned integration-environment receipt(s)`,
      );
      renderChangeset(task);
      showApproval(
        `Apply ${changeset.preview.items.length} verified change(s)`,
        `${changeset.changeset_id} · rollback journal required`,
        "Apply changeset",
      );
      return;
    }
    if (task.outcome === "publication_approval_required") {
      const proposal = task.publication_proposal.document.payload;
      current.phase = "publication";
      current.publicationId = proposal.proposal_id;
      renderSteps([
        ["succeeded", "Apply, reverify, and commit exact changes", "local delivery"],
        ["succeeded", "Observe configured remote through credential broker", "no mutation"],
        ["waiting", "Approve exact push and draft change request", "external action"],
        ["waiting", "Verify provider receipt and finish lifecycle", "postcondition"],
      ]);
      renderText(
        publicationText(proposal, task.publication_proposal.approval_sha256),
        "Separate publication approval required",
        `${proposal.verification_evidence_ids.length} verification receipt(s) bound`,
      );
      showApproval(
        `Publish ${proposal.commit_object_ids.length} verified commit(s)`,
        `${proposal.remote_name} · ${proposal.target_ref} · ${proposal.credential_ref}`,
        "Publish and open draft PR",
      );
      return;
    }
    if (["reverification_completed", "local_commit_completed"].includes(task.outcome)) {
      const committed = task.outcome === "local_commit_completed";
      const diagnostics = task.postapply_runtime_diagnostics || [];
      const databases = task.postapply_database_receipts || [];
      const integrations = task.postapply_integration_environment ? 1 : 0;
      current.rollbackRequired = false;
      current.phase = committed && task.rollback_checkpoint ? "rollback" : null;
      current.rollbackId = task.rollback_checkpoint?.rollback_id || null;
      renderSteps([
        ["succeeded", "Understand and inspect repository", "observe"],
        ["succeeded", "Generate and verify candidate", "verify candidate"],
        ["succeeded", "Apply approved changeset", "modify owner workspace"],
        ["succeeded", (diagnostics.length || databases.length || integrations)
          ? "Reverify deterministic result, diagnostics, database, and integration state"
          : "Reverify deterministic result", "verify result"],
        ...(committed
          ? [["succeeded", "Commit the approved verified changes", "local Git"]]
          : []),
      ]);
      renderText(
        committed
          ? "The approved changeset was applied, passed post-apply verification, and was committed locally with the verification evidence bound to the commit action."
          : "The approved changeset was applied to the owner workspace and passed post-apply verification.",
        committed ? "Applied, reverified, and committed" : "Applied and reverified",
        `${task.postapply_verifications.length} verifier, ${diagnostics.length} runtime diagnostic, ${databases.length} database, and ${integrations} cleaned integration-environment post-apply receipt(s)`,
      );
      if (current.phase === "rollback") {
        const rollback = task.rollback_checkpoint;
        showApproval(
          `Optional rollback of ${rollback.paths.length} path(s)`,
          `${rollback.rollback_id} · creates a separate local rollback commit`,
          "Rollback committed changes",
        );
      } else {
        hideApproval();
      }
      return;
    }
    if (task.outcome === "postapply_verification_failed" && task.rollback_checkpoint) {
      const rollback = task.rollback_checkpoint;
      current.phase = "rollback";
      current.rollbackRequired = true;
      current.rollbackId = rollback.rollback_id;
      renderSteps([
        ["succeeded", "Understand, generate, and verify candidate", "candidate"],
        ["succeeded", "Apply the exact approved changeset", "owner workspace"],
        ["failed", "Reverify the applied owner workspace", "verification failure"],
        ["waiting", "Approve exact pre-commit rollback", "recovery action"],
      ]);
      renderText(
        `Post-apply verification failed (${task.failure_code}). The changed paths remain uncommitted. FAM preserved and diagnosed incident ${task.incident?.payload?.incident_id || "unavailable"}; approve the exact rollback to restore only unchanged FAM-owned paths.`,
        "Rollback approval required",
        `${(task.incident_evidence || []).length} incident evidence receipt(s) recorded`,
      );
      showApproval(
        `Restore ${rollback.paths.length} uncommitted path(s)`,
        `${rollback.rollback_id} · ${rollback.consequences.join(" · ")}`,
        "Rollback failed changes",
      );
      return;
    }
    current.phase = null;
    hideApproval();
    if (task.outcome === "rollback_completed") {
      const committed = Boolean(task.git_rollback_delivery);
      renderSteps([
        ["succeeded", "Apply and verify approved changes", "original delivery"],
        ["succeeded", "Restore exact FAM-owned paths", "journal rollback"],
        ["succeeded", committed
          ? "Commit rollback without rewriting history"
          : "Preserve unchanged Git history", "local Git"],
      ]);
      renderText(
        `The exact approved rollback restored unchanged FAM-owned paths and ${committed ? "created a separate local rollback commit" : "left Git history unchanged"}. Unrelated owner work was preserved.`,
        "Rollback completed", committed
          ? "Rollback and Git receipts recorded"
          : "Rollback and incident closure receipts recorded",
      );
      return;
    }
    if (task.outcome === "publication_completed") {
      const receipt = task.publication_receipt?.payload;
      renderSteps([
        ["succeeded", "Commit exact verified changes", "local Git"],
        ["succeeded", "Use separately approved publication grant", "external action"],
        ["succeeded", "Verify remote provider receipt", "postcondition"],
      ]);
      renderText(
        receipt
          ? `The exact verified object ${receipt.published_new_object_id} was published to ${receipt.remote_name} ${receipt.target_ref}. Draft change request: ${receipt.change_request_url || "provider did not return a URL"}.`
          : "The exact publication completed and its durable receipt was recorded.",
        "Publication completed", "Single-use approval consumed; terminal receipt recorded",
      );
      return;
    }
    if (task.outcome === "analysis_ready") {
      const plan = task.architecture_plan;
      const planText = plan
        ? [
            plan.title,
            ...plan.decisions.map(item =>
              `${item.area}: ${item.decision}\nEvidence: ${item.evidence_refs.join(", ")}`),
            plan.affected_test_paths.length
              ? `Affected tests: ${plan.affected_test_paths.join(", ")}` : "",
            "You can now say “Implement the plan.” in this same workspace and browser session.",
          ].filter(Boolean).join("\n\n")
        : "Repository analysis is ready. The request did not grant modification authority, so no candidate or owner effect was created.";
      renderText(
        limit(planText, 16000), "Analysis and plan complete",
        plan ? "Repository-grounded plan saved for this session" : "No effects executed",
      );
      return;
    }
    if (task.outcome === "answer_ready") {
      current.phase = null;
      renderSteps([
        ["succeeded", "Inspect selected repository evidence", "read only"],
        ["succeeded", "Generate a local-model answer", "Ask mode"],
      ]);
      renderText(
        limit(task.answer, 16000), "Repository-grounded answer",
        `${task.tool_result_count} read-only tool result(s) · no effects executed`,
      );
      hideApproval();
      return;
    }
    if (task.outcome === "runtime_diagnostics_completed") {
      const diagnostics = task.runtime_diagnostics || [];
      const kinds = diagnostics.map(item => item.payload?.signed_recipe_id || "diagnostic");
      renderSteps([
        ["succeeded", "Understand and inspect repository", "observe"],
        ["succeeded", "Select installed signed diagnostic recipes", "Core policy"],
        ["succeeded", "Run bounded candidate diagnostics", "no owner mutation"],
      ]);
      renderText(
        `FAM completed ${diagnostics.length} bounded runtime diagnostic run(s): ${kinds.join(", ")}. Artifacts were sanitized and retained only in the isolated candidate workspace.`,
        "Runtime diagnostics complete",
        `${diagnostics.length} signed, authorized diagnostic receipt(s)`,
      );
      return;
    }
    const incident = task.incident?.payload;
    const incidentText = incident
      ? ` Durable incident ${incident.incident_id} is ${incident.stage}; symptom evidence: ${(incident.symptom_evidence_ids || []).join(", ") || "none"}.`
      : "";
    renderText(
      `FAM stopped safely: ${task.failure_code || task.outcome || "engineering task failed"}.${incidentText}`,
      "Action not completed", incident ? "Failure and incident recorded" : "Failure recorded",
    );
  }

  function checkpointText(task) {
    const plan = task.generation?.summary || "Generated repository changes";
    const items = task.changeset.payload.preview.items;
    return limit(`${plan}\n\n${items.length} exact file change(s) are shown below.`, 16000);
  }

  function renderChangeset(task) {
    current.turn.answerShell.querySelector(".changeset-preview")?.remove();
    const section = document.createElement("section");
    section.className = "changeset-preview";
    const heading = document.createElement("h4");
    heading.textContent = "Proposed changes";
    section.append(heading);
    for (const item of task.changeset.payload.preview.items) {
      const details = document.createElement("details");
      details.open = task.changeset.payload.preview.items.length <= 3;
      const summary = document.createElement("summary");
      const operation = document.createElement("span");
      operation.textContent = item.operation_kind.replaceAll("_", " ");
      const path = document.createElement("strong");
      path.textContent = item.path;
      const risks = document.createElement("small");
      risks.textContent = item.risk_codes.length
        ? item.risk_codes.join(" · ") : "verified candidate";
      summary.append(operation, path, risks);
      const diff = document.createElement("pre");
      diff.textContent = limit(item.preview, 12000);
      details.append(summary, diff);
      section.append(details);
    }
    current.turn.answerShell.append(section);
  }

  function publicationText(proposal, digest) {
    return limit([
      `${proposal.title}\n${proposal.body}`,
      `Remote: ${proposal.remote_name}`,
      `Source: ${proposal.source_ref}`,
      `Target: ${proposal.target_ref}`,
      `Expected old object: ${proposal.expected_old_object_id || "absent (new branch)"}`,
      `Proposed new object: ${proposal.proposed_new_object_id}`,
      `Commits: ${proposal.commit_object_ids.join(", ")}`,
      `Complete diff SHA-256: ${proposal.complete_diff_sha256}`,
      `Remote URL SHA-256: ${proposal.remote_url_sha256}`,
      `Credential reference: ${proposal.credential_ref} (opaque; no secret value exposed)`,
      `Verification: ${proposal.verification_evidence_ids.join(", ")}`,
      `Consequences:\n- ${proposal.consequence_preview.join("\n- ")}`,
      `Approval digest: ${digest}`,
    ].join("\n\n"), 16000);
  }

  function withhold() {
    const checkpoint = current.phase === "changeset";
    const review = current.phase === "review";
    const publication = current.phase === "publication";
    const resources = current.phase === "resources";
    const rollback = current.phase === "rollback";
    const rollbackRequired = rollback && current.rollbackRequired;
    current.phase = null;
    hideApproval();
    renderText(
      review
        ? "The independent review finding remains open and the changeset cannot be applied."
      : checkpoint
        ? "The verified candidate was withheld. The owner workspace was not changed."
        : publication
          ? "The separately proposed push and draft PR were withheld. The verified local commit was kept and no external mutation occurred."
        : rollback
          ? rollbackRequired
            ? "The failed applied changes remain in the workspace. The offered rollback was not executed."
            : "The local verified commit was kept. The optional rollback was not executed."
        : resources
          ? "The proposed integration network and opaque-secret scope was not activated. No process, network, secret, or repository effect occurred."
          : "The proposed engineering authority was not activated. No action was executed.",
      review ? "Review finding remains blocking"
      : rollbackRequired
        ? "Failed changes remain applied"
        : rollback || publication ? "Committed result kept" : "Withheld by owner",
      review ? "No waiver or changeset effect executed"
      : rollback ? "No rollback effect executed" : publication ? "No publication effect executed" : "No effects executed",
    );
  }

  function renderText(content, status, evidence) {
    const turn = current.turn;
    turn.answer.textContent = content;
    turn.accessible.textContent = content;
    turn.answerShell.classList.remove("pending", "typing");
    turn.state.textContent = status;
    turn.meta.classList.remove("hidden");
    turn.assurance.textContent = status;
    turn.evidence.textContent = evidence;
  }

  function renderSteps(steps) {
    byId("empty-activity").classList.add("hidden");
    byId("spine").classList.remove("hidden");
    byId("task-title").textContent = "Natural-language engineering";
    byId("cancel").classList.add("hidden");
    const template = byId("step-template");
    byId("spine").replaceChildren(...steps.map((step, index) => {
      const node = template.content.cloneNode(true);
      const item = node.querySelector("li");
      item.dataset.state = step[0];
      node.querySelector("small").textContent = `${String(index + 1).padStart(2, "0")} / ${step[0]}`;
      node.querySelector("h3").textContent = step[1];
      node.querySelector("p").textContent = step[2];
      return node;
    }));
  }

  function showApproval(summary, scope, label) {
    byId("approval").classList.remove("hidden");
    byId("approval-summary").textContent = summary;
    byId("approval-scope").textContent = scope;
    byId("approve").textContent = label;
  }

  function hideApproval() {
    byId("approval").classList.add("hidden");
    byId("approve").textContent = "Approve action";
  }

  function limit(value, maximum) {
    return value.length <= maximum
      ? value : `${value.slice(0, maximum)}\n… preview truncated in Console`;
  }

  return {configure, start, restore, decide, active, running, steer, cancel};
})();
