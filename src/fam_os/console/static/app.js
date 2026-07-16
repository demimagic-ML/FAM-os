const state={snapshot:null,section:"resources"};
const labels={resources:"Resources",experts:"Experts",permissions:"Permissions",memory:"Memory",audit:"Audit history",recovery:"Recovery"};
const token=new URLSearchParams(location.hash.slice(1)).get("token")||sessionStorage.getItem("fam-console-token");
if(token){sessionStorage.setItem("fam-console-token",token);history.replaceState(null,"",location.pathname)}
async function load(){
  const response=await fetch("/api/v1/snapshot",{headers:{Authorization:`Bearer ${token||""}`}});
  if(!response.ok)throw new Error(`Console access failed (${response.status})`);
  state.snapshot=await response.json();document.querySelector("#connection").textContent="Local / live";
  document.querySelector("#owner").textContent=`UID ${state.snapshot.owner_uid}`;document.querySelector("#release").textContent=state.snapshot.release_id;renderNav();render();
}
function renderNav(){const rail=document.querySelector("#rail");rail.replaceChildren(...state.snapshot.sections.map(section=>{const button=document.createElement("button");button.className="nav-item";button.textContent=labels[section.section_id];button.ariaCurrent=section.section_id===state.section;button.onclick=()=>{state.section=section.section_id;renderNav();render()};return button}))}
function render(){const section=state.snapshot.sections.find(item=>item.section_id===state.section);document.querySelector("#section-title").textContent=section.title;document.querySelector("#section-kicker").textContent=state.snapshot.recovery_mode?"Offline recovery":"Live state";const template=document.querySelector("#card");const cards=section.items.map(item=>{const node=template.content.cloneNode(true);node.querySelector(".status").classList.add(item.status);node.querySelector("small").textContent=item.status;node.querySelector("h3").textContent=item.label;node.querySelector("strong").textContent=item.value;node.querySelector("p").textContent=item.detail||"Observed locally";return node});document.querySelector("#cards").replaceChildren(...cards)}
document.querySelector("#refresh").onclick=()=>load().catch(fail);function fail(error){document.querySelector("#connection").textContent=error.message;document.querySelector(".pulse i").style.background="var(--red)"}load().catch(fail);
