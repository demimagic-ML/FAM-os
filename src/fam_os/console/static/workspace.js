"use strict";

const FamWorkspace = (() => {
  let api = null;
  let contexts = [];
  let current = null;
  let browsing = null;
  let onSelected = () => {};
  let activityKey = null;

  const byId = id => document.getElementById(id);

  function configure(request, options = {}) {
    api = request;
    onSelected = options.onSelected || onSelected;
    byId("open-workspace").onclick = () => open().catch(showError);
    byId("close-workspace").onclick = close;
    byId("workspace-form").onsubmit = event => {
      event.preventDefault();
      browse(byId("workspace-location").value.trim()).catch(showError);
    };
    byId("workspace-parent").onclick = () => {
      if (browsing?.parent_path) browse(browsing.parent_path).catch(showError);
    };
    byId("select-workspace").onclick = selectCurrent;
    byId("use-workspace-root").onclick = () => {
      if (current) selectResource(current);
    };
  }

  function updateContexts(next) {
    contexts = next;
    const available = Boolean(filesystemContext());
    byId("open-workspace").disabled = !available;
    if (!available) {
      byId("workspace-path").textContent = "The local filesystem connector is unavailable.";
    }
  }

  async function open() {
    byId("workspace-message").textContent = "";
    byId("workspace-dialog").showModal();
    await browse(current?.path || "");
  }

  function close() {
    byId("workspace-dialog").close();
  }

  async function browse(path) {
    const suffix = path ? `?path=${encodeURIComponent(path)}` : "";
    browsing = await api(`/api/v1/workspace${suffix}`);
    byId("workspace-location").value = browsing.path;
    byId("workspace-browser-path").textContent = browsing.path;
    byId("workspace-parent").disabled = !browsing.parent_path;
    byId("workspace-message").textContent = browsing.truncated
      ? `Showing the first ${browsing.maximum_entries} entries.` : "";
    renderBrowser();
  }

  function renderBrowser() {
    const rows = browsing.entries.filter(item => item.kind === "directory").map(item => {
      const button = entryButton(item);
      button.onclick = () => browse(item.path).catch(showError);
      return button;
    });
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.textContent = "This folder has no child folders. You can still use it.";
      empty.className = "workspace-browser-empty";
      byId("workspace-browser").replaceChildren(empty);
      return;
    }
    byId("workspace-browser").replaceChildren(...rows);
  }

  function selectCurrent() {
    if (!browsing || !workspaceContext(browsing.uri)) return;
    current = browsing;
    renderWorkspace();
    selectResource(current);
    close();
  }

  function renderWorkspace() {
    const card = byId("workspace-authority");
    card.classList.add("selected");
    card.querySelector(".workspace-state").textContent = "Folder authority selected";
    byId("workspace-name").textContent = current.display_name;
    byId("workspace-path").textContent = current.path;
    byId("use-workspace-root").classList.remove("hidden");
    byId("workspace-file-count").textContent = current.truncated
      ? `${current.entries.length}+ entries` : `${current.entries.length} entries`;
    const rows = current.entries.map(item => {
      const button = entryButton(item);
      if (item.selectable) button.onclick = () => selectResource(item);
      else button.disabled = true;
      return button;
    });
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.textContent = "This folder is empty.";
      rows.push(empty);
    }
    byId("workspace-file-list").replaceChildren(...rows);
  }

  function entryButton(item) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "workspace-entry";
    const type = document.createElement("i");
    type.textContent = item.kind === "directory" ? "D" : item.kind === "file" ? "F" : "—";
    const name = document.createElement("b");
    name.textContent = item.name;
    const detail = document.createElement("small");
    detail.textContent = item.kind === "file" ? formatBytes(item.size_bytes) : item.kind;
    button.append(type, name, detail);
    return button;
  }

  function selectResource(resource) {
    const context = workspaceContext(current?.uri || resource.uri);
    if (!context) return;
    onSelected(context, resource);
    byId("workspace-authority").querySelector(".workspace-state").textContent = resource.uri === current?.uri
      ? "Folder authority selected" : `${resource.kind || "resource"} selected`;
  }

  function filesystemContext() {
    return contexts.find(item => item.application_id === "fam.local.filesystem");
  }

  function workspaceContext(workspaceUri) {
    return contexts.find(item =>
      item.workspace_resource_ref === workspaceUri
      && (item.observation_capability_ids || []).includes("os.directory.list"),
    ) || filesystemContext();
  }

  async function loadActivity(taskId, revision) {
    const key = `${taskId}:${revision}`;
    if (activityKey === key) return;
    const document = await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/activity`);
    activityKey = key;
    renderActivity(document.items || []);
  }

  function resetActivity() {
    activityKey = null;
    const item = document.createElement("li");
    item.className = "terminal-empty";
    const prompt = document.createElement("span");
    prompt.textContent = "fam:";
    const message = document.createElement("p");
    message.textContent = "Waiting for deterministic tool evidence.";
    item.append(prompt, message);
    byId("tool-activity").replaceChildren(item);
  }

  function selectedPath() {
    return current?.path || null;
  }

  function renderActivity(items) {
    if (!items.length) {
      resetActivity();
      return;
    }
    byId("tool-activity").replaceChildren(...items.map(item => {
      const row = document.createElement("li");
      row.dataset.status = item.status;
      const head = document.createElement("header");
      const label = document.createElement("strong");
      label.textContent = item.label;
      const status = document.createElement("span");
      status.textContent = item.status.replaceAll("_", " ");
      const output = document.createElement("pre");
      output.textContent = formatOutput(item);
      head.append(label, status);
      row.append(head, output);
      return row;
    }));
  }

  function formatOutput(item) {
    const value = item.output || {};
    if (Array.isArray(value.entries)) {
      const lines = value.entries.slice(0, 80).map(entry =>
        `${entry.kind === "directory" ? "d" : "-"} ${entry.name}`,
      );
      if (value.truncated || value.entries.length > 80) lines.push("… bounded listing truncated");
      return clean(`$ list ${value.path || item.resource_uri || ""}\n${lines.join("\n")}`);
    }
    if (typeof value.content === "string") {
      return clean(`$ read ${value.path || item.resource_uri || ""}\n${limit(value.content, 6000)}`);
    }
    if (value.executable) {
      return clean(`$ ${[value.executable, ...(value.arguments || [])].join(" ")}\napproval preview · not executed yet`);
    }
    if ("stdout" in value || "stderr" in value) {
      return clean(`$ ${item.capability_id}\nexit ${value.exit_code}\n${limit(value.stdout || value.stderr || "", 6000)}`);
    }
    return clean(limit(JSON.stringify(value, null, 2), 6000));
  }

  function clean(value) {
    return String(value).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "�");
  }

  function limit(value, maximum) {
    const text = String(value);
    return text.length <= maximum ? text : `${text.slice(0, maximum)}\n… output truncated in Console`;
  }

  function formatBytes(value) {
    if (!Number.isFinite(value)) return "file";
    if (value < 1024) return `${value} B`;
    if (value < 1048576) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / 1048576).toFixed(1)} MB`;
  }

  function showError(error) {
    byId("workspace-message").textContent = error.message;
  }

  return {configure, updateContexts, loadActivity, resetActivity, selectedPath};
})();
