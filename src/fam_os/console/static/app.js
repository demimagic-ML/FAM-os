const state = {
  csrf: null,
  machine: null,
  contexts: [],
  integrations: [],
  task: null,
  reversal: null,
  events: null,
  pollTimer: null,
  polling: false,
  pollFailures: 0,
  view: "work",
  machineSection: "resources",
  controlSection: "permissions",
  turns: [],
  activeTurn: null,
  typing: null,
};
const labels = {
  resources: "Resources",
  experts: "Experts",
  permissions: "Permissions",
  memory: "Memory",
  audit: "Audit",
  recovery: "Recovery",
};
const $ = selector => document.querySelector(selector);

class RequestError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "RequestError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const headers = {...(options.headers || {})};
  if (options.method && options.method !== "GET") {
    headers["X-CSRF-Token"] = state.csrf;
    headers.Origin = location.origin;
  }
  const response = await fetch(path, {...options, headers});
  if (!response.ok) {
    const body = await response.text();
    let detail = "Request failed.";
    try {
      const parsed = JSON.parse(body);
      if (typeof parsed.error === "string") detail = parsed.error;
    } catch (_) {
      if (response.status === 401) detail = "The local Console session expired. Reopen FAM from its launcher.";
      else if (response.status === 404) detail = "The requested local resource is unavailable.";
    }
    throw new RequestError(response.status, detail);
  }
  return response.json();
}

async function secureSession() {
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  if (token) {
    history.replaceState(null, "", location.pathname);
    const response = await fetch("/api/v1/session", {
      method: "POST",
      headers: {Authorization: `Bearer ${token}`, Origin: location.origin},
      body: "{}",
    });
    if (!response.ok) throw new Error("The launcher token was rejected.");
    return response.json();
  }
  return request("/api/v1/session");
}

async function boot() {
  const session = await secureSession();
  state.csrf = session.csrf_token;
  FamMemory.configure(request);
  FamAdaptation.configure(request);
  FamPeers.configure(request);
  [state.machine, {contexts: state.contexts}, {integrations: state.integrations}] =
    await Promise.all([
      request("/api/v1/snapshot"),
      request("/api/v1/contexts"),
      request("/api/v1/integrations"),
    ]);
  $("#connection").textContent = "Local fabric / live";
  $(".runtime").classList.add("live");
  $("#owner").textContent = `UID ${state.machine.owner_uid}`;
  $("#release").textContent = state.machine.release_id;
  renderContexts();
  renderCatalogs();
  renderIntegrations();
  updateScopeSummary();
}

function renderContexts() {
  const select = $("#context");
  const selectedId = select.value;
  const options = [new Option("No application context", "")];
  for (const context of state.contexts) {
    const option = new Option(context.display_name, context.context_id);
    option.dataset.context = JSON.stringify(context);
    options.push(option);
  }
  select.replaceChildren(...options);
  if (options.some(option => option.value === selectedId)) select.value = selectedId;
  FamWorkspace.updateContexts(state.contexts);
  updateScopeSummary();
}

function selectView(view) {
  state.view = view;
  document.querySelectorAll("[data-panel]").forEach(
    panel => panel.classList.toggle("hidden", panel.dataset.panel !== view),
  );
  document.querySelectorAll(".nav-item").forEach(
    item => item.classList.toggle("active", item.dataset.view === view),
  );
  if (view === "adaptation") FamAdaptation.load().catch(fail);
  if (view === "peers") FamPeers.load().catch(fail);
}

function sectionsFor(ids) {
  return state.machine.sections.filter(section => ids.includes(section.section_id));
}

function renderCatalogs() {
  renderCatalog("machine", ["resources", "experts"]);
  renderCatalog("control", ["permissions", "memory", "audit", "recovery"]);
}

function renderCatalog(kind, ids) {
  const active = state[`${kind}Section`];
  const tabs = $(`#${kind}-tabs`);
  tabs.replaceChildren(...sectionsFor(ids).map(section => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = labels[section.section_id];
    button.classList.toggle("active", section.section_id === active);
    button.onclick = () => {
      state[`${kind}Section`] = section.section_id;
      renderCatalog(kind, ids);
    };
    return button;
  }));
  const section = state.machine.sections.find(item => item.section_id === active);
  const template = $("#card-template");
  const cards = (section?.items || []).map(item => {
    const node = template.content.cloneNode(true);
    node.querySelector(".status").classList.add(item.status);
    node.querySelector("small").textContent = item.status;
    node.querySelector("h3").textContent = item.label;
    node.querySelector("strong").textContent = item.value;
    node.querySelector("p").textContent = item.detail || "Observed locally";
    return node;
  });
  const memoryActive = kind === "control" && active === "memory";
  $(`#${kind}-cards`).classList.toggle("hidden", memoryActive);
  if (kind === "control") $("#memory-workspace").classList.toggle("hidden", !memoryActive);
  $(`#${kind}-cards`).replaceChildren(...cards);
  if (memoryActive) FamMemory.load().catch(fail);
}

function renderIntegrations() {
  const template = $("#card-template");
  const cards = state.integrations.map(item => {
    const node = template.content.cloneNode(true);
    const degraded = item.actions_requested && !item.actions_active;
    const status = item.active && !degraded ? "active" : (item.configured ? "attention" : "inactive");
    node.querySelector(".status").classList.add(status);
    node.querySelector("small").textContent = status;
    node.querySelector("h3").textContent = item.mechanism.replaceAll("_", " ");
    node.querySelector("strong").textContent = item.configured
      ? (item.actions_active ? "Observation + confirmed action" : "Observation only")
      : "Disabled by default";
    const scopes = item.resource_scopes.length ? item.resource_scopes.join(", ") : "no approved targets";
    const actions = item.action_primitives.length
      ? ` Actions: ${item.action_primitives.join(", ")}; confirmation ${item.confirmation}.`
      : " No action authority.";
    node.querySelector("p").textContent = `${item.privacy_impact}. Scope: ${scopes}.${actions}${item.issue_code ? ` Status: ${item.issue_code}.` : ""}`;
    return node;
  });
  $("#integration-cards").replaceChildren(...cards);
}

function selectedTaskContext() {
  const option = $("#context").selectedOptions[0];
  return option?.dataset.context ? JSON.parse(option.dataset.context) : null;
}

function updateScopeSummary() {
  const selected = selectedTaskContext();
  const resource = $("#resource").value.trim();
  const profile = $("#agent-profile").value;
  const profileLabel = {
    ask: "Ask", workspace: "Workspace", full_os: "Full OS",
  }[profile];
  const parts = [profileLabel, FamWorkspace.selectedPath() ? "Workspace agent" : "Application task"];
  parts.push(selected ? selected.display_name : "Local machine");
  if (resource) parts.push("specific resource");
  if ($("#verify").checked) parts.push("verified");
  $("#scope-summary").textContent = parts.join(" · ");
}

function contextLabel(selected, resource) {
  const parts = [selected ? selected.display_name : "Local machine"];
  if (resource) parts.push(resource);
  return parts.join(" · ");
}

function finishTyping() {
  if (!state.typing) return;
  state.typing.finish();
  state.typing = null;
}

function scrollToTurn(turn, reducedMotion = false) {
  FamConversation.scrollMessageStart($("#transcript"), turn.fam, {
    reducedMotion,
    padding: 22,
  });
}

function startTurn(prompt, scope, taskId) {
  finishTyping();
  setSubmissionStatus("");
  FamWorkspace.resetActivity();
  const fragment = $("#turn-template").content.cloneNode(true);
  const user = fragment.querySelector(".user-turn");
  const fam = fragment.querySelector(".fam-turn");
  user.querySelector(".turn-context").textContent = scope;
  user.querySelector(".user-message").textContent = prompt;
  fam.dataset.taskId = taskId;
  fam.querySelector(".answer-text").textContent = "Working through the plan…";
  fam.querySelector(".answer-shell").classList.add("pending");
  $("#empty-task").classList.add("hidden");
  $("#transcript").append(fragment);
  const turn = {
    taskId,
    user,
    fam,
    resultKey: null,
    answer: fam.querySelector(".answer-text"),
    accessible: fam.querySelector(".answer-accessible"),
    answerShell: fam.querySelector(".answer-shell"),
    state: fam.querySelector(".turn-state"),
    meta: fam.querySelector(".result-meta"),
    assurance: fam.querySelector(".turn-assurance"),
    evidence: fam.querySelector(".turn-evidence"),
    citations: fam.querySelector(".citations"),
  };
  state.turns.push(turn);
  state.activeTurn = turn;
  requestAnimationFrame(() => scrollToTurn(turn));
  return turn;
}

function resetEngineeringTranscript() {
  finishTyping();
  state.turns = [];
  state.activeTurn = null;
  $("#transcript").querySelectorAll(".user-turn,.fam-turn").forEach(node => node.remove());
  $("#empty-task").classList.remove("hidden");
  FamWorkspace.resetActivity();
}

function setComposerBusy(busy, label = "") {
  const form = $("#task-form");
  const button = $("#send-task");
  button.disabled = busy;
  button.classList.toggle("is-busy", busy);
  button.querySelector("span:first-child").textContent = label || (busy ? "Task running" : "Send task");
  form.setAttribute("aria-busy", String(busy));
}

function setSubmissionStatus(message, state = "") {
  const status = $("#submission-status");
  status.textContent = message;
  status.dataset.state = state;
  status.classList.toggle("hidden", !message);
}

async function createTask(event) {
  event.preventDefault();
  const prompt = $("#prompt").value.trim();
  if (!prompt || $("#send-task").disabled) return;
  setComposerBusy(true, "Sending…");
  setSubmissionStatus("Task accepted locally. Resolving the request…", "pending");
  const selected = selectedTaskContext();
  const workspacePath = FamWorkspace.selectedPath();
  let resolved;
  try {
    resolved = await request("/api/v1/conversation/resolve", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({prompt}),
    });
  } catch (error) {
    setComposerBusy(false);
    setSubmissionStatus(`Task was not accepted: ${error.message || "request failed"}`, "failed");
    throw error;
  }
  setSubmissionStatus("Request understood. Starting the local agent…", "pending");
  if (workspacePath) {
    stopTaskWatch();
    state.task = null;
    try {
      await FamNaturalEngineering.start(
        resolved.resolved_request,
        contextLabel(selected, workspacePath), workspacePath,
        $("#agent-profile").value,
      );
    } catch (error) {
      setComposerBusy(false);
      setSubmissionStatus(`The local agent could not start: ${error.message || "request failed"}`, "failed");
      throw error;
    }
    $("#prompt").value = "";
    resizePrompt();
    selectView("work");
    $("#prompt").focus();
    return;
  }
  if (resolved?.disposition === "repository_change") {
    setComposerBusy(false);
    setSubmissionStatus("Choose a folder before starting this workspace task.", "failed");
    throw new Error("Choose a folder for this workspace task.");
  }
  const context = selected ? {
    context_id: selected.context_id,
    kind: selected.kind,
    resource_ref: selected.resource_ref,
    display_name: selected.display_name,
    // Core resolves least authority from the prompt. The client must declare the
    // complete live surface or previewed workspace actions can never be selected.
    capability_ids: selected.capability_ids,
  } : null;
  const contexts = context ? [context] : [];
  const explicitResource = $("#resource").value.trim();
  const resource = explicitResource || selected?.workspace_resource_ref || "";
  if (resource) {
    contexts.push({
      context_id: selected?.workspace_resource_ref && !explicitResource
        ? `${selected.context_id}-workspace`
        : "selected-resource",
      kind: "uri",
      resource_ref: resource,
      display_name: resource,
      capability_ids: [],
    });
  }
  const body = {
    prompt: resolved.resolved_request,
    contexts,
    verification_required: $("#verify").checked,
  };
  try {
    state.task = await request("/api/v1/tasks", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
  } catch (error) {
    setComposerBusy(false);
    setSubmissionStatus(`The task could not start: ${error.message || "request failed"}`, "failed");
    throw error;
  }
  startTurn(prompt, contextLabel(selected, explicitResource), state.task.session_id);
  $("#prompt").value = "";
  resizePrompt();
  selectView("work");
  renderTask();
  if (state.task.state !== "terminal") watchTask();
  $("#prompt").focus();
}

function watchTask() {
  stopTaskWatch();
  state.pollFailures = 0;
  state.events = new EventSource(`/api/v1/tasks/${encodeURIComponent(state.task.session_id)}/events`);
  state.events.addEventListener("task", event => {
    state.pollFailures = 0;
    updateTask(JSON.parse(event.data));
  });
  state.events.onerror = () => {
    if (state.events) {
      state.events.close();
      state.events = null;
    }
    schedulePoll(0);
  };
  schedulePoll(2000);
}

function updateTask(next) {
  if (!FamTaskUpdates.accepts(state.task, next)) return;
  const changed = !state.task || next.revision !== state.task.revision ||
    next.state !== state.task.state || next.message !== state.task.message;
  state.task = next;
  if (changed) renderTask();
  if (next.state === "terminal") stopTaskWatch();
}

function schedulePoll(delay = 2000) {
  if (!state.task || state.task.state === "terminal" || state.pollTimer !== null) return;
  state.pollTimer = setTimeout(() => {
    state.pollTimer = null;
    pollTask().catch(fail);
  }, delay);
}

async function pollTask() {
  if (!state.task || state.task.state === "terminal" || state.polling) return;
  state.polling = true;
  try {
    updateTask(await request(`/api/v1/tasks/${encodeURIComponent(state.task.session_id)}`));
    state.pollFailures = 0;
    $("#connection").textContent = "Local fabric / live";
    $(".runtime").classList.add("live");
    schedulePoll();
  } catch (error) {
    if (error instanceof RequestError && error.status === 401) {
      expireConsoleSession();
      return;
    }
    state.pollFailures += 1;
    $("#connection").textContent = `Task update interrupted / retrying (${state.pollFailures})`;
    $(".runtime").classList.remove("live");
    schedulePoll(Math.min(5000, 500 * (2 ** Math.min(state.pollFailures, 4))));
  } finally {
    state.polling = false;
  }
}

function stopTaskWatch() {
  if (state.events) {
    state.events.close();
    state.events = null;
  }
  if (state.pollTimer !== null) {
    clearTimeout(state.pollTimer);
    state.pollTimer = null;
  }
}

function expireConsoleSession() {
  stopTaskWatch();
  $("#connection").textContent = "Console session expired / reopen from launcher";
  $(".runtime").classList.remove("live");
  $("#task-title").textContent = "Task status unavailable";
  $("#cancel").classList.add("hidden");
  setComposerBusy(false);
}

function renderTask() {
  const task = state.task;
  $("#empty-activity").classList.add("hidden");
  $("#spine").classList.remove("hidden");
  $("#task-title").textContent = task.message || "Working locally";
  $("#cancel").classList.toggle("hidden", task.state === "terminal");
  setComposerBusy(task.state !== "terminal");
  if (state.activeTurn) {
    state.activeTurn.state.textContent = task.result
      ? FamTaskUpdates.resultPresentation(task.result).label
      : task.message || task.state.replaceAll("_", " ");
    state.activeTurn.fam.dataset.state = task.state;
  }
  const template = $("#step-template");
  $("#spine").replaceChildren(...task.steps.map((step, index) => {
    const node = template.content.cloneNode(true);
    const item = node.querySelector("li");
    const displayState = FamTaskUpdates.displayStepState(task.state, step.state);
    item.dataset.state = displayState;
    node.querySelector("small").textContent = `${String(index + 1).padStart(2, "0")} / ${displayState.replaceAll("_", " ")}`;
    node.querySelector("h3").textContent = step.description;
    node.querySelector("p").textContent = step.kind.replaceAll("_", " ");
    return node;
  }));
  renderApproval(task.approval);
  renderResult(task.result);
  const presentation = task.result
    ? FamTaskUpdates.resultPresentation(task.result)
    : null;
  if (task.state === "terminal" && presentation?.canReverse) {
    loadReversal().catch(fail);
  } else {
    state.reversal = null;
    $("#undo").classList.add("hidden");
  }
  FamWorkspace.loadActivity(task.session_id, task.revision).catch(error => {
    if (!(error instanceof RequestError && error.status === 404)) fail(error);
  });
}

function renderApproval(approval) {
  $("#approval").classList.toggle("hidden", !approval);
  if (!approval) return;
  $("#approval-summary").textContent = approval.summary;
  $("#approval-scope").textContent = `Capability ${approval.capability_id} · ${approval.reversible ? "reversible" : "not reversible"}`;
}

function renderResult(result) {
  const turn = state.activeTurn;
  if (!result || !turn) return;
  const content = result.content || result.reason || "The task finished without a released answer.";
  const resultKey = JSON.stringify([
    result.status,
    result.result_kind,
    content,
    result.assurance,
    result.evidence_ids,
    result.citations,
  ]);
  if (turn.resultKey === resultKey) return;
  finishTyping();
  turn.resultKey = resultKey;
  turn.accessible.textContent = content;
  turn.answerShell.classList.remove("pending");
  turn.answerShell.classList.add("typing");
  turn.meta.classList.remove("hidden");
  const presentation = FamTaskUpdates.resultPresentation(result);
  turn.state.textContent = presentation.label;
  turn.assurance.textContent = presentation.label;
  const evidenceIds = result.evidence_ids || [];
  turn.evidence.textContent = presentation.evidenceLabel;
  renderCitations(turn, result.citations || []);
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  scrollToTurn(turn, reducedMotion);
  const typing = FamConversation.revealText(turn.answer, content, {
    reducedMotion,
    onComplete: () => {
      turn.answerShell.classList.remove("typing");
      scrollToTurn(turn, reducedMotion);
      state.typing = null;
    },
  });
  if (turn.answerShell.classList.contains("typing")) state.typing = typing;
}

function renderCitations(turn, citations) {
  turn.citations.classList.toggle("hidden", !citations.length);
  turn.citations.querySelector("ol").replaceChildren(...citations.map(citation => {
    const item = document.createElement("li");
    const source = document.createElement("strong");
    source.textContent = `${citation.source_locator} · characters ${citation.start_character}-${citation.end_character}`;
    const claim = document.createElement("p");
    claim.textContent = citation.claim_text;
    const quote = document.createElement("blockquote");
    quote.textContent = citation.quoted_text;
    item.append(source, claim, quote);
    return item;
  }));
}

async function loadReversal() {
  if (!state.task) return;
  state.reversal = await request(`/api/v1/tasks/${encodeURIComponent(state.task.session_id)}/reversal`);
  $("#undo").classList.toggle("hidden", !state.reversal.available);
}

async function undoTask() {
  if (!state.task || !state.reversal?.available) return;
  const body = {
    request_id: crypto.randomUUID(),
    expected_revision: state.reversal.expected_revision,
  };
  state.task = await request(`/api/v1/tasks/${encodeURIComponent(state.task.session_id)}/undo`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  state.reversal = null;
  $("#undo").classList.add("hidden");
  renderTask();
  watchTask();
}

async function decide(decision) {
  const approval = state.task.approval;
  if (!approval) return;
  state.task = await request(`/api/v1/tasks/${encodeURIComponent(state.task.session_id)}/decision`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      expected_revision: state.task.revision,
      approval_id: approval.approval_id,
      decision,
    }),
  });
  renderTask();
  watchTask();
}

async function cancelTask() {
  state.task = await request(`/api/v1/tasks/${encodeURIComponent(state.task.session_id)}/cancel`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({expected_revision: state.task.revision}),
  });
  renderTask();
}

async function refresh() {
  [state.machine, {contexts: state.contexts}, {integrations: state.integrations}] =
    await Promise.all([
      request("/api/v1/snapshot"),
      request("/api/v1/contexts"),
      request("/api/v1/integrations"),
    ]);
  renderContexts();
  renderCatalogs();
  renderIntegrations();
}

function resizePrompt() {
  const prompt = $("#prompt");
  prompt.style.height = "auto";
  prompt.style.height = `${Math.min(180, prompt.scrollHeight)}px`;
}

function selectWorkspaceResource(context, resource) {
  const select = $("#context");
  if ([...select.options].some(option => option.value === context.context_id)) {
    select.value = context.context_id;
  }
  $("#resource").value = resource.uri;
  updateScopeSummary();
  const workspacePath = FamWorkspace.selectedPath();
  if (workspacePath) {
    FamNaturalEngineering.restore(
      workspacePath, contextLabel(context, workspacePath),
    ).catch(fail);
  }
  $("#prompt").focus();
}

function fail(error) {
  $("#connection").textContent = error.message || "Local request failed.";
  $(".runtime").classList.remove("live");
}

document.querySelectorAll(".nav-item").forEach(
  item => item.onclick = () => selectView(item.dataset.view),
);
$("#task-form").onsubmit = event => createTask(event).catch(fail);
$("#approve").onclick = () => (
  FamNaturalEngineering.active()
    ? FamNaturalEngineering.decide(true) : decide("approve")
).catch(fail);
$("#deny").onclick = () => (
  FamNaturalEngineering.active()
    ? FamNaturalEngineering.decide(false) : decide("deny")
).catch(fail);
$("#cancel").onclick = () => (
  FamNaturalEngineering.running()
    ? FamNaturalEngineering.cancel() : cancelTask()
).catch(fail);
$("#steer-agent").onclick = () => FamNaturalEngineering.steer().catch(fail);
$("#undo").onclick = () => undoTask().catch(fail);
$("#refresh").onclick = () => refresh().catch(fail);
$("#context").onchange = updateScopeSummary;
$("#agent-profile").onchange = updateScopeSummary;
$("#resource").oninput = updateScopeSummary;
$("#verify").onchange = updateScopeSummary;
$("#prompt").oninput = resizePrompt;
$("#prompt").onkeydown = event => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    $("#task-form").requestSubmit();
  }
};
FamWorkspace.configure(request, {onSelected: selectWorkspaceResource});
  FamNaturalEngineering.configure(request, {
    startTurn, setBusy: setComposerBusy,
    resetTranscript: resetEngineeringTranscript,
  });
  FamUsefulTasks.configure(request);
  FamIntegrationCenter.configure(request);
  FamProductivity.configure(request);
  boot().catch(fail);
