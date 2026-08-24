# ruff: noqa: E501
import json

from fastapi.responses import HTMLResponse

from house_brain.languages import language_family
from house_brain.web_theme import (
    SHARED_THEME_CSS,
    browser_security_headers,
    shared_navigation,
)

MESSAGES = {
    "en": {
        "title": "Installation management",
        "subtitle": "Back up, inspect and safely restore the persistent configuration.",
        "login": "Sign in",
        "api_key": "API key",
        "intro": "The key stays only in this browser tab.",
        "logout": "Sign out",
        "status": "Installation status",
        "refresh": "Refresh",
        "backup": "Backup",
        "backup_intro": "Create a coherent archive after policy and SQLite validation.",
        "download": "Create and download backup",
        "restore": "Restore",
        "restore_intro": "Upload an archive for inspection. Nothing is changed during inspection.",
        "choose": "Choose backup archive",
        "inspect": "Inspect archive",
        "files": "Files that would be replaced",
        "confirm": "Type RESTORE to confirm",
        "apply": "Apply staged restore",
        "ready": "Ready",
        "attention": "Attention required",
        "loading": "Loading…",
        "invalid_key": "Missing or invalid API key.",
        "error": "Error: ",
        "created": "Backup created.",
        "inspected": "Archive validated. Review the replacement list.",
        "restored": "Restore completed. Restart the container before further use.",
        "policy": "Policy",
        "database": "Database",
        "storage": "Persistent storage",
        "schema": "Installation schema",
        "updates": "Updates",
        "manual": "Manual, with operator-controlled rollback",
        "no_file": "Choose a ZIP archive first.",
    },
    "it": {
        "title": "Gestione installazione",
        "subtitle": "Esegui backup, ispeziona e ripristina in sicurezza la configurazione persistente.",
        "login": "Accedi",
        "api_key": "Chiave API",
        "intro": "La chiave rimane soltanto nella sessione di questa scheda.",
        "logout": "Esci",
        "status": "Stato installazione",
        "refresh": "Aggiorna",
        "backup": "Backup",
        "backup_intro": "Crea un archivio coerente dopo la verifica della policy e di SQLite.",
        "download": "Crea e scarica backup",
        "restore": "Ripristino",
        "restore_intro": "Carica un archivio per ispezionarlo. Durante l'ispezione non viene modificato nulla.",
        "choose": "Scegli archivio di backup",
        "inspect": "Ispeziona archivio",
        "files": "File che verranno sostituiti",
        "confirm": "Scrivi RESTORE per confermare",
        "apply": "Applica ripristino preparato",
        "ready": "Pronta",
        "attention": "Richiede attenzione",
        "loading": "Caricamento…",
        "invalid_key": "Chiave API mancante o non valida.",
        "error": "Errore: ",
        "created": "Backup creato.",
        "inspected": "Archivio verificato. Controlla l'elenco delle sostituzioni.",
        "restored": "Ripristino completato. Riavvia il container prima di continuare.",
        "policy": "Policy",
        "database": "Database",
        "storage": "Archiviazione persistente",
        "schema": "Schema installazione",
        "updates": "Aggiornamenti",
        "manual": "Manuali, con rollback controllato dall'operatore",
        "no_file": "Seleziona prima un archivio ZIP.",
    },
}

HTML = """<!doctype html><html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__ · House Brain</title><style>
main{max-width:1180px;margin:auto;padding:28px 18px 60px}.header{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap}.panel{margin-top:16px;padding:20px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.metric{padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--panel-2)}.metric strong{display:block;font-size:1.15rem;margin-top:5px}.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}.status{min-height:24px;margin-top:10px;color:var(--muted)}.error{color:var(--danger)}.hidden{display:none!important}input[type=password]{min-width:260px}input[type=file]{max-width:100%}ul{padding-left:22px;max-height:320px;overflow:auto}code{overflow-wrap:anywhere}.warning{padding:12px;border-left:4px solid var(--hb-warning);background:var(--panel-2);border-radius:8px}
</style></head><body><main><header class="header"><div><h1>__TITLE__</h1><p>__SUBTITLE__</p></div><button id="logout" class="hidden">__LOGOUT__</button></header>
<section id="auth" class="panel"><form id="authForm"><p>__INTRO__</p><div class="actions"><input id="apiKey" type="password" autocomplete="current-password" placeholder="__API_KEY__" required><button class="primary">__LOGIN__</button></div><div id="authError" class="status error"></div></form></section>
<section id="app" class="hidden">
<section class="panel"><div class="header"><div><h2>__STATUS__</h2></div><button id="refresh">__REFRESH__</button></div><div id="metrics" class="grid"></div><div id="statusMessage" class="status"></div></section>
<section class="panel"><h2>__BACKUP__</h2><p>__BACKUP_INTRO__</p><div class="actions"><button id="download" class="primary">__DOWNLOAD__</button></div><div id="backupStatus" class="status"></div></section>
<section class="panel"><h2>__RESTORE__</h2><p>__RESTORE_INTRO__</p><div class="warning">__MANUAL__</div><div class="actions"><input id="archive" type="file" accept=".zip,application/zip"><button id="inspect">__INSPECT__</button></div><div id="restoreStatus" class="status"></div><div id="staged" class="hidden"><h3>__FILES__</h3><ul id="files"></ul><div class="actions"><input id="confirmation" type="text" autocomplete="off" placeholder="__CONFIRM__"><button id="apply" class="primary">__APPLY__</button></div></div></section>
</section>
<script>(()=>{"use strict";const i18n=__I18N__,KEY="house_brain_api_key";let restoreToken=null;const $=id=>document.getElementById(id),apiKey=()=>(sessionStorage.getItem(KEY)||"").trim();
async function api(path,options={}){const headers=new Headers(options.headers||{});headers.set("X-API-Key",apiKey());headers.set("Accept","application/json");return fetch(path,{...options,headers})}async function payload(response){const text=await response.text();if(!text)return{};try{return JSON.parse(text)}catch(error){throw new Error(response.ok?response.statusText:text.slice(0,300))}}function setMessage(node,text,error=false){node.textContent=text;node.className="status"+(error?" error":"")}function authError(error){sessionStorage.removeItem(KEY);$("authError").textContent=i18n.error+(error?.message||String(error));$("auth").classList.remove("hidden");$("app").classList.add("hidden");$("logout").classList.add("hidden")}
function metric(label,value){const box=document.createElement("div"),small=document.createElement("span"),strong=document.createElement("strong");box.className="metric";small.textContent=label;strong.textContent=value;box.append(small,strong);return box}
async function load(){setMessage($("statusMessage"),i18n.loading);const response=await api("/admin/installation");const body=await payload(response);if(response.status===401||response.status===403)throw new Error(i18n.invalid_key);if(!response.ok)throw new Error(body.detail||response.statusText);$("metrics").replaceChildren(metric(i18n.storage,body.persistent_root_access),metric(i18n.policy,body.policy),metric(i18n.database,body.database),metric(i18n.schema,String(body.installation_schema_version)),metric(i18n.updates,i18n.manual));setMessage($("statusMessage"),body.status==="ready"?i18n.ready:i18n.attention,body.status!=="ready");$("auth").classList.add("hidden");$("app").classList.remove("hidden");$("logout").classList.remove("hidden")}
$("authForm").addEventListener("submit",async event=>{event.preventDefault();$("authError").textContent="";const key=$("apiKey").value.trim();if(!key){authError(new Error(i18n.invalid_key));return}sessionStorage.setItem(KEY,key);try{await load()}catch(error){authError(error)}});
$("refresh").addEventListener("click",()=>load().catch(error=>setMessage($("statusMessage"),i18n.error+error.message,true)));
$("download").addEventListener("click",async()=>{const button=$("download");button.disabled=true;setMessage($("backupStatus"),i18n.loading);try{const response=await api("/admin/installation/backups",{method:"POST"});if(!response.ok){const body=await payload(response);throw new Error(body.detail||response.statusText)}const blob=await response.blob(),link=document.createElement("a"),disposition=response.headers.get("Content-Disposition")||"",match=/filename="?([^";]+)"?/.exec(disposition);link.href=URL.createObjectURL(blob);link.download=match?.[1]||"house-brain-config-backup.zip";link.click();URL.revokeObjectURL(link.href);setMessage($("backupStatus"),i18n.created)}catch(error){setMessage($("backupStatus"),i18n.error+error.message,true)}finally{button.disabled=false}});
$("inspect").addEventListener("click",async()=>{const file=$("archive").files[0];if(!file){setMessage($("restoreStatus"),i18n.no_file,true);return}const button=$("inspect");button.disabled=true;restoreToken=null;$("staged").classList.add("hidden");setMessage($("restoreStatus"),i18n.loading);try{const response=await api("/admin/installation/restores/inspect",{method:"POST",headers:{"Content-Type":"application/zip"},body:file});const body=await payload(response);if(!response.ok)throw new Error(body.detail||response.statusText);restoreToken=body.restore_token;$("files").replaceChildren();for(const item of body.files){const row=document.createElement("li");row.textContent=item.path+" · "+item.size+" bytes";$("files").append(row)}$("confirmation").value="";$("staged").classList.remove("hidden");setMessage($("restoreStatus"),i18n.inspected)}catch(error){setMessage($("restoreStatus"),i18n.error+error.message,true)}finally{button.disabled=false}});
$("apply").addEventListener("click",async()=>{if(!restoreToken||$("confirmation").value!=="RESTORE"){setMessage($("restoreStatus"),i18n.confirm,true);return}const button=$("apply");button.disabled=true;setMessage($("restoreStatus"),i18n.loading);try{const response=await api("/admin/installation/restores/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({restore_token:restoreToken,confirmation:"RESTORE"})});const body=await payload(response);if(!response.ok)throw new Error(body.detail||response.statusText);restoreToken=null;$("staged").classList.add("hidden");setMessage($("restoreStatus"),i18n.restored);await load()}catch(error){setMessage($("restoreStatus"),i18n.error+error.message,true)}finally{button.disabled=false}});
$("logout").addEventListener("click",()=>{sessionStorage.removeItem(KEY);location.reload()});if(apiKey())load().catch(authError)})();</script></main></body></html>"""


def installation_page(
    language: str,
    frame_ancestor: str | None = None,
) -> HTMLResponse:
    family = language_family(language)
    messages = MESSAGES.get(family, MESSAGES["en"])
    html = HTML.replace("__LANG__", family).replace(
        "__I18N__",
        json.dumps(messages, ensure_ascii=True).replace("<", "\\u003c"),
    )
    for key, value in messages.items():
        html = html.replace(f"__{key.upper()}__", value)
    html = html.replace("</style>", f"{SHARED_THEME_CSS}</style>", 1)
    html = html.replace(
        "<body>",
        f'<body class="hb-installation">{shared_navigation("installation", language)}',
        1,
    )
    return HTMLResponse(
        html,
        headers=browser_security_headers(frame_ancestor),
    )
