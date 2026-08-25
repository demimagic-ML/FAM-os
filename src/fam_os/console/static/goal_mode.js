"use strict";

const FamGoalMode = (() => {
  let api = null;
  let hooks = null;
  let current = null;
  let timer = null;

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
    const goal = (payload.goals || []).find(item => !["cancelled"].includes(item.status));
    if (!goal || current?.goal?.goal_id === goal.goal_id) return;
    const turn = hooks.startTurn(goal.prompt, `Goal mode · ${scope}`, goal.goal_id);
    current = {goal, turn};
    renderGoal(goal);
    if (goal.status === "draft") {
      renderPlan(goal);
      byId("goal-dialog").showModal();
    } else if (["queued", "running", "pause_requested", "cancel_requested"].includes(goal.status)) {
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
      running: `Goal running in background · execution epoch ${goal.epochs}.`,
      pause_requested: "Pausing safely after the current model step…",
      paused: "Goal paused. Resume when you are ready.",
      cancel_requested: "Cancelling safely after the current model step…",
      cancelled: "Goal cancelled. Completed evidence remains available.",
      waiting_approval: "Goal needs an owner decision before it can continue.",
      completed: "Goal completed and the verified changes were applied.",
      failed: `Goal stopped: ${goal.error || "the requested outcome was not verified"}`,
    };
    current.turn.answer.textContent = labels[goal.status] || `Goal status: ${goal.status}`;
    current.turn.state.textContent = goal.status.replaceAll("_", " ");
    current.turn.answerShell.classList.toggle("pending", [
      "queued", "running", "pause_requested", "cancel_requested",
    ].includes(goal.status));
    current.turn.meta.classList.remove("hidden");
    current.turn.assurance.textContent = "DURABLE GOAL";
    current.turn.evidence.textContent = `${goal.plan.length} PLAN STEPS · ${goal.acceptance_criteria.length} COMPLETION CHECKS`;
    hooks.goalActivity(goal, control);
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

  function watch() {
    clearInterval(timer);
    timer = setInterval(() => refresh().catch(hooks.fail), 1000);
    refresh().catch(hooks.fail);
  }

  async function refresh() {
    if (!current) return;
    const goal = await api(`/api/v1/goals/${encodeURIComponent(current.goal.goal_id)}/inspect`);
    renderGoal(goal);
    if (["completed", "cancelled", "failed", "paused", "waiting_approval"].includes(goal.status)) {
      clearInterval(timer);
      timer = null;
    }
  }

  function revise() {
    if (!current) return;
    byId("goal-dialog").close();
    byId("prompt").value = current.goal.prompt;
    byId("prompt").focus();
  }

  return {configure, prepare, restore, control};
})();
