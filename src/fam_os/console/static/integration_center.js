const FamIntegrationCenter = (() => {
  let api;
  const byId = id => document.getElementById(id);
  function configure(request) {
    api = request;
    byId("integration-center-cards").onclick = event => act(event).catch(showError);
    load().catch(showError);
  }
  async function load() {
    const {integrations} = await api("/api/v1/integration-center/catalog");
    byId("integration-center-cards").replaceChildren(...integrations.map(card));
  }
  function card(item) {
    const article = document.createElement("article");
    const top = document.createElement("div");
    const status = document.createElement("span");
    status.className = "status";
    status.textContent = item.state?.status || (item.runtime_available ? "available" : "runtime missing");
    const kind = document.createElement("small");
    kind.textContent = item.integration_id;
    top.append(status, kind);
    const title = document.createElement("h3"); title.textContent = item.title;
    const command = document.createElement("strong"); command.textContent = item.command;
    const description = document.createElement("p"); description.textContent = item.description;
    const button = document.createElement("button");
    button.className = "quiet"; button.type = "button";
    button.dataset.integration = item.integration_id;
    button.dataset.operation = item.configured ? "test" : "configure";
    button.textContent = item.configured ? "Test connection" : "Configure";
    article.append(top, title, command, description, button);
    return article;
  }
  async function act(event) {
    const button = event.target.closest("[data-integration]"); if (!button) return;
    const id = encodeURIComponent(button.dataset.integration);
    const operation = button.dataset.operation;
    let document = {};
    if (operation === "configure" && ["mcp.filesystem", "mcp.git"].includes(button.dataset.integration)) {
      const root = window.prompt(button.dataset.integration === "mcp.git" ? "Repository folder" : "Approved folder");
      if (!root) return;
      document = {enabled:true, configuration:{roots:[root]}};
    } else if (operation === "configure" && button.dataset.integration === "mcp.time") {
      document = {enabled:true, configuration:{timezone:Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"}};
    } else if (operation === "configure") {
      document = {enabled:true, configuration:{}};
    }
    const options = {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(document)};
    const result = await api(`/api/v1/integration-center/${id}/${operation}`, options);
    byId("integration-center-message").textContent = result.error || `${button.dataset.integration}: ${result.status}`;
    await load();
  }
  function showError(error) { byId("integration-center-message").textContent = error.message; }
  return {configure};
})();
