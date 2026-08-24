const FamProductivity = (() => {
  let api, recipes = [];
  const byId = id => document.getElementById(id);
  function configure(request) {
    api = request;
    byId("recipe-cards").onclick = event => runRecipe(event).catch(showRecipeError);
    byId("automation-form").onsubmit = event => saveAutomation(event).catch(showAutomationError);
    byId("automation-list").onclick = event => runAutomation(event).catch(showAutomationError);
    byId("automation-refresh").onclick = () => loadAutomations().catch(showAutomationError);
    load().catch(showRecipeError);
  }
  async function load() {
    const workflowResult = await api("/api/v1/useful/workflows");
    byId("automation-workflow").replaceChildren(...workflowResult.workflows.map(item => {
      const option = document.createElement("option"); option.value = item.workflow_id;
      option.textContent = item.title; return option;
    }));
    const result = await api("/api/v1/recipes"); recipes = result.recipes;
    byId("recipe-cards").replaceChildren(...recipes.map(recipeCard));
    await loadAutomations();
  }
  function recipeCard(recipe) {
    const article = document.createElement("article");
    const top = document.createElement("div"); const status = document.createElement("span");
    status.className="status"; status.textContent=recipe.builtin?"built in":"personal";
    const id=document.createElement("small"); id.textContent=recipe.recipe_id; top.append(status,id);
    const title=document.createElement("h3"); title.textContent=recipe.name;
    const description=document.createElement("p"); description.textContent=recipe.description;
    const button=document.createElement("button"); button.type="button"; button.className="quiet";
    button.dataset.recipe=recipe.recipe_id; button.textContent="Use recipe";
    article.append(top,title,description,button); return article;
  }
  async function runRecipe(event) {
    const button=event.target.closest("[data-recipe]"); if(!button)return;
    const workspace=window.prompt("Workspace folder"); if(!workspace)return;
    const recipe=recipes.find(item=>item.recipe_id===button.dataset.recipe);
    const inputs={workspace_root:workspace};
    if(recipe.request_template.workflow_id==="research.cited-brief"){
      const urls=window.prompt("Source URLs, separated by spaces"); if(!urls)return;
      inputs.urls=urls.split(/\s+/).filter(Boolean);
    }
    const task=await api(`/api/v1/recipes/${encodeURIComponent(button.dataset.recipe)}/run`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(inputs)});
    byId("recipe-message").textContent=task.summary||task.error;
  }
  async function saveAutomation(event) {
    event.preventDefault(); const type=byId("automation-trigger").value;
    const trigger={type}; if(type==="interval")trigger.seconds=Number(byId("automation-seconds").value);
    if(type==="file_changed")trigger.path=byId("automation-path").value;
    await api("/api/v1/automations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:byId("automation-name").value,request:{workflow_id:byId("automation-workflow").value,prompt:byId("automation-prompt").value,workspace_root:byId("automation-root").value},trigger,run_mode:byId("automation-mode").value})});
    byId("automation-message").textContent="Automation saved."; await loadAutomations();
  }
  async function loadAutomations(){const result=await api("/api/v1/automations");byId("automation-list").replaceChildren(...(result.automations.length?result.automations.map(automationCard):[empty()]));}
  function automationCard(item){const article=document.createElement("article");article.className="useful-task-card";const title=document.createElement("h3");title.textContent=item.name;const detail=document.createElement("p");detail.textContent=`${item.trigger.type} · ${item.run_mode} · ${item.last_status||"not run"}`;const button=document.createElement("button");button.type="button";button.className="quiet";button.dataset.automation=item.automation_id;button.textContent="Run now";article.append(title,detail,button);return article;}
  async function runAutomation(event){const button=event.target.closest("[data-automation]");if(!button)return;const result=await api(`/api/v1/automations/${encodeURIComponent(button.dataset.automation)}/run`,{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});byId("automation-message").textContent=`Run ${result.status}`;await loadAutomations();}
  function empty(){const value=document.createElement("p");value.textContent="No automation saved yet.";return value;}
  function showRecipeError(error){byId("recipe-message").textContent=error.message;}
  function showAutomationError(error){byId("automation-message").textContent=error.message;}
  return {configure};
})();
