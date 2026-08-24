# ruff: noqa: E501

import json

from fastapi.responses import HTMLResponse

from house_brain.languages import language_family
from house_brain.web_theme import (
    SHARED_THEME_CSS,
    browser_security_headers,
    shared_navigation,
)

_MESSAGES = {
    "it": {
        "title": "Viste contestuali",
        "subtitle": "Prepara contesti piccoli e deterministici senza ampliare i permessi di Autonomia.",
        "login": "Accedi", "intro": "La chiave rimane soltanto nella sessione di questa scheda.",
        "api_key": "Chiave API", "logout": "Esci", "add": "Nuova vista", "save": "Salva configurazione",
        "default": "Vista predefinita", "none": "Nessuna", "enabled": "Abilitata",
        "name": "Nome", "identifier": "Identificatore", "areas": "Aree", "domains": "Domini",
        "entities": "Entità", "limit": "Limite entità", "memories": "Includi memorie collegate",
        "preview": "Anteprima", "remove": "Rimuovi", "empty": "Nessuna vista configurata.",
        "saved": "Configurazione salvata.", "confirm_remove": "Rimuovere questa vista?",
        "policy": "Le viste possono solo restringere le entità già visibili in Autonomia.",
        "selected": "entità selezionate", "omitted": "omesse dal limite", "error": "Errore: ",
        "invalid_key": "Chiave API non valida.", "comma": "Valori separati da virgole",
        "save_first": "Salva la configurazione prima di visualizzare l\'anteprima delle modifiche.",
    },
    "en": {
        "title": "Context views",
        "subtitle": "Build small deterministic contexts without expanding Autonomy permissions.",
        "login": "Sign in", "intro": "The key remains only in this tab session.",
        "api_key": "API key", "logout": "Sign out", "add": "New view", "save": "Save configuration",
        "default": "Default view", "none": "None", "enabled": "Enabled",
        "name": "Name", "identifier": "Identifier", "areas": "Areas", "domains": "Domains",
        "entities": "Entities", "limit": "Entity limit", "memories": "Include linked memories",
        "preview": "Preview", "remove": "Remove", "empty": "No views configured.",
        "saved": "Configuration saved.", "confirm_remove": "Remove this view?",
        "policy": "Views can only narrow entities already visible in Autonomy.",
        "selected": "entities selected", "omitted": "omitted by limit", "error": "Error: ",
        "invalid_key": "Invalid API key.", "comma": "Comma-separated values",
        "save_first": "Save the configuration before previewing changes.",
    },
}
_LANGUAGE_FALLBACK = {
    "ar": "en", "de": "en", "es": "en", "fr": "en", "ja": "en",
    "ko": "en", "pt": "en", "zh": "en",
}

HTML = r"""<!doctype html>
<html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>House Brain · __TITLE__</title>
<style>
.shell{width:min(1180px,100%);margin:auto;padding:18px}.panel{padding:18px;margin-bottom:14px}
header{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:18px;margin-bottom:14px}
h1,h2{margin:.1rem 0}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.grid{display:grid;gap:12px}.view{padding:16px;border:1px solid var(--hb-divider);border-radius:12px;background:var(--hb-card-alt)}
.fields{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.wide{grid-column:1/-1}
label{display:grid;gap:5px;color:var(--hb-muted)}label.check{display:flex;align-items:center;gap:8px;color:var(--hb-text)}
input[type=checkbox]{width:18px;height:18px;accent-color:var(--hb-primary)}input,select{width:100%;padding:9px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.status{min-height:1.5em;color:var(--hb-muted)}
.error{color:var(--hb-error)}.notice{padding:12px;border-left:4px solid var(--hb-primary);background:var(--hb-primary-soft);margin-bottom:14px}
.preview{margin-top:10px;padding:10px;border-radius:8px;background:var(--hb-card);color:var(--hb-muted)}
[hidden]{display:none!important}@media(max-width:700px){.fields{grid-template-columns:1fr}.wide{grid-column:1}}
</style></head><body>__NAV__<div class="shell">
<header><div><h1>__TITLE__</h1><p>__SUBTITLE__</p></div><button id="logout" hidden>__LOGOUT__</button></header>
<section class="panel" id="auth"><h2>__LOGIN__</h2><p>__INTRO__</p><form class="row" id="authForm">
<input id="apiKey" type="password" placeholder="__API_KEY__" required><button class="primary">__LOGIN__</button></form><div id="authError" class="status error"></div></section>
<main id="editor" hidden><div class="notice">__POLICY__</div><section class="panel">
<div class="row"><label style="min-width:220px">__DEFAULT__<select id="defaultView"></select></label>
<button id="add" type="button">__ADD__</button><button class="primary" id="save" type="button">__SAVE__</button></div>
<div id="status" class="status"></div></section><section class="panel"><div id="views" class="grid"></div><p id="empty">__EMPTY__</p></section></main>
</div><script>
(()=>{"use strict";const M=__MESSAGES__,KEY="house_brain_api_key";let state={version:1,default_view:null,views:[]},dirty=false;
const $=id=>document.getElementById(id),key=()=>sessionStorage.getItem(KEY)||"";
async function api(path,opt={}){const h=new Headers(opt.headers||{});h.set("X-API-Key",key());h.set("Accept","application/json");if(opt.body)h.set("Content-Type","application/json");const r=await fetch(path,{...opt,headers:h});const t=await r.text();let b={};try{b=t?JSON.parse(t):{}}catch{throw new Error(t.slice(0,240)||r.statusText)}if(!r.ok)throw new Error(r.status===401?M.invalid_key:(b.detail||r.statusText));return b}
const split=v=>[...new Set(v.split(",").map(x=>x.trim()).filter(Boolean))];
function slug(v){return v.toLowerCase().trim().replace(/[^a-z0-9_-]+/g,"_").replace(/^_+|_+$/g,"").slice(0,64)}
function field(label,value,cls=""){const l=document.createElement("label");l.className=cls;l.textContent=label;const i=document.createElement("input");i.value=value||"";i.placeholder=M.comma;l.append(i);return [l,i]}
function render(){const root=$("views");root.replaceChildren();$("empty").hidden=state.views.length>0;
state.views.forEach((view,index)=>{const card=document.createElement("article");card.className="view";const fields=document.createElement("div");fields.className="fields";
const [nameL,name]=field(M.name,view.name);const [idL,id]=field(M.identifier,view.id);const [areasL,areas]=field(M.areas,(view.areas||[]).join(", "), "wide");const [domainsL,domains]=field(M.domains,(view.domains||[]).join(", "), "wide");const [entitiesL,entities]=field(M.entities,(view.entities||[]).join(", "), "wide");
const limitL=document.createElement("label");limitL.textContent=M.limit;const limit=document.createElement("input");limit.type="number";limit.min="1";limit.max="100";limit.value=view.max_entities||50;limitL.append(limit);
const enabledL=document.createElement("label");enabledL.className="check";const enabled=document.createElement("input");enabled.type="checkbox";enabled.checked=view.enabled!==false;enabledL.append(enabled,M.enabled);
const memoriesL=document.createElement("label");memoriesL.className="check";const memories=document.createElement("input");memories.type="checkbox";memories.checked=view.include_linked_memories!==false;memoriesL.append(memories,M.memories);
fields.append(nameL,idL,areasL,domainsL,entitiesL,limitL,enabledL,memoriesL);card.append(fields);
const actions=document.createElement("div");actions.className="actions";const preview=document.createElement("button");preview.type="button";preview.textContent=M.preview;const remove=document.createElement("button");remove.type="button";remove.className="danger";remove.textContent=M.remove;const out=document.createElement("div");out.className="preview";out.hidden=true;
function sync(mark=true){view.name=name.value.trim();view.id=slug(id.value||name.value);id.value=view.id;view.areas=split(areas.value);view.domains=split(domains.value).map(x=>x.toLowerCase());view.entities=split(entities.value).map(x=>x.toLowerCase());view.max_entities=Number(limit.value)||50;view.enabled=enabled.checked;view.include_linked_memories=memories.checked;if(mark)dirty=true;refreshDefault()}
for(const x of [name,id,areas,domains,entities,limit,enabled,memories])x.addEventListener("change",sync);
preview.onclick=async()=>{sync(false);out.hidden=false;if(dirty){out.textContent=M.save_first;out.classList.add("error");return}out.classList.remove("error");out.textContent="…";try{const b=await api("/admin/context-views/"+encodeURIComponent(view.id)+"/preview");out.textContent=b.selected_before_limit+" "+M.selected+", "+b.omitted_by_view_limit+" "+M.omitted}catch(e){out.textContent=M.error+e.message;out.classList.add("error")}};
remove.onclick=()=>{if(confirm(M.confirm_remove)){state.views.splice(index,1);if(state.default_view===view.id)state.default_view=null;dirty=true;render()}};
actions.append(preview,remove);card.append(actions,out);root.append(card)});refreshDefault()}
function refreshDefault(){const s=$("defaultView"),current=state.default_view;s.replaceChildren(new Option(M.none,""));for(const v of state.views)s.add(new Option(v.name+" ("+v.id+")",v.id));s.value=current||""}
async function load(){const b=await api("/admin/context-views");state=b.configuration;dirty=false;render();$("auth").hidden=true;$("editor").hidden=false;$("logout").hidden=false}
$("authForm").onsubmit=async e=>{e.preventDefault();sessionStorage.setItem(KEY,$("apiKey").value.trim());try{await load()}catch(err){sessionStorage.removeItem(KEY);$("authError").textContent=M.error+err.message}};
$("add").onclick=()=>{let n=state.views.length+1,id="context_view_"+n;while(state.views.some(v=>v.id===id))id="context_view_"+(++n);state.views.push({id,name:"Context view "+n,enabled:true,areas:[],domains:[],entities:[],max_entities:50,include_linked_memories:true});dirty=true;render()};
$("defaultView").onchange=e=>{state.default_view=e.target.value||null;dirty=true};
$("save").onclick=async()=>{for(const input of $("views").querySelectorAll("input"))input.dispatchEvent(new Event("change"));$("status").textContent="";try{const b=await api("/admin/context-views",{method:"PUT",body:JSON.stringify(state)});state=b.configuration;dirty=false;render();$("status").classList.remove("error");$("status").textContent=M.saved}catch(e){$("status").textContent=M.error+e.message;$("status").classList.add("error")}};
$("logout").onclick=()=>{sessionStorage.removeItem(KEY);location.reload()};if(key())load().catch(()=>sessionStorage.removeItem(KEY));
})();
</script></body></html>"""


def context_views_page(language: str, frame_ancestor: str | None = None) -> HTMLResponse:
    """Return the authenticated context-view management interface."""
    family = language_family(language)
    messages = _MESSAGES.get(family, _MESSAGES[_LANGUAGE_FALLBACK.get(family, "en")])
    html = HTML.replace("__LANG__", family).replace("__NAV__", shared_navigation("context", language))
    html = html.replace("__MESSAGES__", json.dumps(messages, ensure_ascii=True).replace("<", "\\u003c"))
    for key, value in messages.items():
        html = html.replace(f"__{key.upper()}__", value)
    html = html.replace("</style>", f"{SHARED_THEME_CSS}</style>", 1)
    return HTMLResponse(html, headers=browser_security_headers(frame_ancestor))
