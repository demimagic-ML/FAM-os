const FamUsefulTasks = (() => {
  let api;
  const byId = id => document.getElementById(id);

  function configure(request) {
    api = request;
    byId("useful-form").onsubmit = event => run(event).catch(showError);
    byId("useful-refresh").onclick = () => loadTasks().catch(showError);
    byId("useful-search").oninput = () => loadTasks().catch(showError);
    byId("useful-attention").onchange = () => loadTasks().catch(showError);
    byId("useful-tasks").onclick = event => taskAction(event).catch(showError);
    load().catch(showError);
  }

  async function load() {
    const [{workflows}] = await Promise.all([
      api("/api/v1/useful/workflows"), loadTasks(),
    ]);
    byId("useful-workflow").replaceChildren(...workflows.map(item => {
      const option = document.createElement("option");
      option.value = item.workflow_id;
      option.textContent = `${item.title} — ${item.description}`;
      return option;
    }));
  }

  async function run(event) {
    event.preventDefault();
    const button = byId("useful-run");
    button.disabled = true;
    message("Running locally…");
    try {
      const task = await api("/api/v1/useful/tasks/submit", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          workflow_id: byId("useful-workflow").value,
          prompt: byId("useful-prompt").value,
          workspace_root: byId("useful-root").value,
          input_paths: lines(byId("useful-inputs").value) || undefined,
          urls: lines(byId("useful-urls").value) || undefined,
        }),
      });
      message(`Task ${task.status}. You can keep working while it runs.`);
      await loadTasks();
    } finally {
      button.disabled = false;
    }
  }

  async function loadTasks() {
    const query = new URLSearchParams({limit: "30"});
    if (byId("useful-search").value.trim()) query.set("q", byId("useful-search").value.trim());
    if (byId("useful-attention").checked) query.set("attention", "true");
    const result = await api(`/api/v1/useful/tasks?${query}`);
    byId("useful-tasks").replaceChildren(...(
      result.tasks.length ? result.tasks.map(card) : [empty()]
    ));
  }

  function card(task) {
    const article = document.createElement("article");
    article.className = "useful-task-card";
    const header = document.createElement("header");
    const title = document.createElement("h3");
    title.textContent = task.workflow_id;
    const status = document.createElement("strong");
    status.textContent = task.status;
    header.append(title, status);
    const summary = document.createElement("p");
    summary.textContent = task.summary || task.error || "Running";
    const artifacts = document.createElement("div");
    artifacts.className = "useful-artifacts";
    artifacts.replaceChildren(...task.artifacts.map(item => {
      const code = document.createElement("code");
      code.textContent = item.path;
      code.dataset.artifact = item.artifact_id;
      code.tabIndex = 0;
      return code;
    }));
    const actions = document.createElement("div");
    actions.className = "useful-artifacts";
    actions.append(action("Retry", "retry", task.task_id), action("Fork", "fork", task.task_id), action("Save recipe", "recipe", task.task_id));
    if (task.status === "running") actions.append(action("Cancel", "cancel", task.task_id));
    article.append(header, summary, artifacts, actions);
    return article;
  }

  function action(label, operation, task) {
    const button = document.createElement("button"); button.type = "button";
    button.className = "quiet"; button.textContent = label;
    button.dataset.taskAction = operation; button.dataset.task = task; return button;
  }

  async function taskAction(event) {
    const artifact = event.target.closest("[data-artifact]");
    if (artifact) {
      const result = await api(`/api/v1/useful/artifacts/${encodeURIComponent(artifact.dataset.artifact)}`);
      const preview = byId("useful-preview"); preview.textContent = result.content || result.path;
      preview.classList.remove("hidden"); return;
    }
    const button = event.target.closest("[data-task-action]"); if (!button) return;
    if (button.dataset.taskAction === "recipe") {
      const name = window.prompt("Recipe name"); if (!name) return;
      const description = window.prompt("What is this recipe for?", "Reusable workflow") || "Reusable workflow";
      await api("/api/v1/recipes", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({name, description, source_task_id:button.dataset.task})});
      message("Recipe saved."); return;
    }
    let body = {};
    if (button.dataset.taskAction === "fork") {
      const prompt = window.prompt("New task instructions"); if (!prompt) return;
      body = {prompt};
    }
    await api(`/api/v1/useful/tasks/${encodeURIComponent(button.dataset.task)}/${button.dataset.taskAction}`, {
      method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body),
    });
    await loadTasks();
  }

  function empty() {
    const value = document.createElement("p");
    value.textContent = "No useful workflow has run yet.";
    return value;
  }

  function lines(value) {
    const items = value.split("\n").map(item => item.trim()).filter(Boolean);
    return items.length ? items : null;
  }

  function message(value) { byId("useful-message").textContent = value || ""; }
  function showError(error) { message(error.message); }
  return {configure};
})();
