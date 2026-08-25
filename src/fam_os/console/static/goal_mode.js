"use strict";

const FamGoalMode = (() => {
  let api = null;
  let hooks = null;
  let current = null;
  let timer = null;
  let events = null;

  const byId = id => document.getElementById(id);

  function configure(request, options) {
    api = request;
    hooks = options;
    byId("goal-close").onclick = () => byId("goal-dialog").close();
    byId("goal-revise").onclick = revise;
    byId("goal-activate").onclick = () => activate().catch(hooks.fail);
  }

  async function prepare(prompt, workspaceRoot, authorityProfile, scope) {
    if (!workspaceRoot) throw new Error("Choose a workspace folder before using Goal mode.");
    const turn = hooks.startTurn(prompt, `Goal mode · ${scope}`, `goal-draft-${Date.now()}`);
    turn.answer.textContent = "Creating a concrete plan and completion criteria…";
    hooks.status("Goal accepted. The local model is preparing its execution plan…", "pending");
    try {
      const goal = await api("/api/v1/goals", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          prompt, workspace_root: workspaceRoot,
          authority_profile: authorityProfile,
        }),
      });
      current = {goal, turn};
      turn.taskId = goal.goal_id;
      turn.fam.dataset.taskId = goal.goal_id;
      renderPlan(goal);
      turn.answer.textContent = "Plan ready. Review it and choose Activate goal when it matches the result you want.";
      hooks.status("");
      hooks.setBusy(false);
      byId("goal-dialog").showModal();
      return goal;
    } catch (error) {
      turn.answer.textContent = `Goal planning failed: ${error.message || "local planning failed"}`;
      hooks.status(`Goal planning failed: ${error.message || "local planning failed"}`, "failed");
      hooks.setBusy(false);
      throw error;
    }
  }

  async function restore(workspaceRoot, scope) {
    if (!workspaceRoot) return;
    const payload = await api(`/api/v1/goals?workspace_root=${encodeURIComponent(workspaceRoot)}`);
    let goal = (payload.goals || []).find(item => !["cancelled"].includes(item.status));
    if (!goal || current?.goal?.goal_id === goal.goal_id) return;
    goal = await api(`/api/v1/goals/${encodeURIComponent(goal.goal_id)}/inspect`);
    const turn = hooks.startTurn(goal.prompt, `Goal mode · ${scope}`, goal.goal_id);
    current = {goal, turn};
    renderGoal(goal);
    if (goal.status === "draft") {
      renderPlan(goal);
      byId("goal-dialog").showModal();
    } else if (["queued", "running", "retry_wait", "pause_requested", "cancel_requested"].includes(goal.status)) {
      watch();
    }
  }

  async function activate() {
    if (!current) return;
    const button = byId("goal-activate");
    button.disabled = true;
    button.textContent = "Activating…";
    try {
      const goal = await api(`/api/v1/goals/${encodeURIComponent(current.goal.goal_id)}/activate`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({confirmed: true}),
      });
      current.goal = goal;
      byId("goal-dialog").close();
      current.turn.answer.textContent = "Goal activated. FAM is continuing in the background; you may close this tab.";
      renderGoal(goal);
      watch();
    } finally {
      button.disabled = false;
      button.textContent = "Activate goal";
    }
  }

  function renderPlan(goal) {
    byId("goal-dialog-title").textContent = goal.title;
    byId("goal-objective").textContent = goal.prompt;
    byId("goal-plan").replaceChildren(...goal.plan.map(textItem));
    byId("goal-criteria").replaceChildren(...goal.acceptance_criteria.map(textItem));
  }

  function textItem(value) {
    const item = document.createElement("li");
    item.textContent = value;
    return item;
  }

  function renderGoal(goal) {
    if (!current) return;
    current.goal = goal;
    const labels = {
      draft: "Plan ready for activation.",
      queued: "Goal queued. The background supervisor is preparing the workspace.",
      retry_wait: recoverySentence(goal),
      running: liveSentence(goal),
      pause_requested: "Pausing safely after the current model step…",
      paused: "Goal paused. Resume when you are ready.",
      cancel_requested: "Cancelling safely after the current model step…",
      cancelled: "Goal cancelled. Completed evidence remains available.",
      waiting_approval: "Goal needs an owner decision before it can continue.",
      completed: "Goal completed and the verified changes were applied.",
      failed: failureSentence(goal),
    };
    current.turn.answer.textContent = labels[goal.status] || `Goal status: ${goal.status}`;
    current.turn.state.textContent = goal.status.replaceAll("_", " ");
    current.turn.answerShell.classList.toggle("pending", [
      "queued", "running", "retry_wait", "pause_requested", "cancel_requested",
    ].includes(goal.status));
    current.turn.meta.classList.remove("hidden");
    current.turn.assurance.textContent = "DURABLE GOAL";
    current.turn.evidence.textContent = `${goal.plan.length} PLAN STEPS · ${goal.acceptance_criteria.length} COMPLETION CHECKS`;
    hooks.goalActivity(goal, control);
  }

  function liveSentence(goal) {
    const live = goal.live;
    if (!live) return `Goal running in background · execution epoch ${goal.epochs}.`;
    const phase = (live.phase || live.node || "working").replaceAll("_", " ");
    const model = live.model_ref ? ` with ${live.model_ref}` : "";
    const evidence = live.result_count ? ` · ${live.result_count} observations retained` : "";
    return `Working in the isolated candidate · ${phase} · model step ${live.step || 0}${model}${evidence}.`;
  }

  function failureSentence(goal) {
    const failure = goal.error || "the requested outcome was not verified";
    if (failure.includes("OllamaTransportError")) {
      return "Goal stopped during verification because the local model connection was interrupted. Candidate work is preserved, and nothing was applied to your workspace.";
    }
    return `Goal stopped before apply: ${failure}. Candidate work is preserved, and the owner workspace remains unchanged.`;
  }

  function recoverySentence(goal) {
    const recovery = goal.recovery || {};
    const seconds = Math.max(0, Math.ceil(
      (Date.parse(recovery.next_retry_at || "") - Date.now()) / 1000,
    ));
    return `Recovering from a temporary model interruption · attempt ${recovery.attempt || 1} · next retry in ${seconds}s. Candidate work and checkpoints are preserved.`;
  }

  async function control(action) {
    if (!current) return;
    const goal = await api(`/api/v1/goals/${encodeURIComponent(current.goal.goal_id)}/control`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action}),
    });
    renderGoal(goal);
    if (action === "resume") watch();
  }

  async function guide(content) {
    if (!current || !content.trim()) return;
    const goal = await api(`/api/v1/goals/${encodeURIComponent(current.goal.goal_id)}/control`, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action: "guide", content: content.trim()}),
    });
    renderGoal(goal);
  }

  function watch() {
    if (events) events.close();
    events = new EventSource(`/api/v1/goals/${encodeURIComponent(current.goal.goal_id)}/events`);
    events.addEventListener("goal", event => renderGoal(JSON.parse(event.data)));
    events.onerror = () => {
      events?.close();
      events = null;
    };
    clearInterval(timer);
    timer = setInterval(() => refresh().catch(hooks.fail), 3000);
    refresh().catch(hooks.fail);
  }

  async function refresh() {
    if (!current) return;
    const goal = await api(`/api/v1/goals/${encodeURIComponent(current.goal.goal_id)}/inspect`);
    renderGoal(goal);
    if (["completed", "cancelled", "failed", "paused", "waiting_approval"].includes(goal.status)) {
      clearInterval(timer);
      timer = null;
      events?.close();
      events = null;
    }
  }

  function revise() {
    if (!current) return;
    byId("goal-dialog").close();
    byId("prompt").value = current.goal.prompt;
    byId("prompt").focus();
  }

  return {configure, prepare, restore, control, guide};
})();
