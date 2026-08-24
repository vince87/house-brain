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
    "en":{"title":"Action audit","subtitle":"Review autonomous events and authoritative tool results.","login":"Sign in","api_key":"API key","intro":"The key stays only in this browser tab.","search":"Search events","all":"All modes","empty":"No events found.","loading":"Loading…","invalid_key":"Missing or invalid API key.","error":"Error: ","logout":"Sign out","instruction":"Instruction","response":"Final response","trace":"Full tool trace","tools":"Tools","status":"Status"},
    "it":{"title":"Audit azioni","subtitle":"Controlla eventi autonomi e risultati autorevoli degli strumenti.","login":"Accedi","api_key":"Chiave API","intro":"La chiave rimane soltanto nella sessione di questa scheda.","search":"Cerca eventi","all":"Tutte le modalità","empty":"Nessun evento trovato.","loading":"Caricamento…","invalid_key":"Chiave API mancante o non valida.","error":"Errore: ","logout":"Esci","instruction":"Istruzione","response":"Risposta finale","trace":"Tool trace completa","tools":"Strumenti","status":"Stato"},
    "de":{"title":"Aktionsaudit","subtitle":"Autonome Ereignisse und maßgebliche Werkzeugergebnisse prüfen.","login":"Anmelden","api_key":"API-Schlüssel","intro":"Der Schlüssel bleibt nur in diesem Tab.","search":"Ereignisse suchen","all":"Alle Modi","empty":"Keine Ereignisse gefunden.","loading":"Laden…","invalid_key":"API-Schlüssel fehlt oder ist ungültig.","error":"Fehler: ","logout":"Abmelden","instruction":"Anweisung","response":"Endgültige Antwort","trace":"Vollständige Werkzeugspur","tools":"Werkzeuge","status":"Status"},
    "es":{"title":"Auditoría de acciones","subtitle":"Revisa eventos autónomos y resultados autorizados.","login":"Acceder","api_key":"Clave API","intro":"La clave permanece solo en esta pestaña.","search":"Buscar eventos","all":"Todos los modos","empty":"No se encontraron eventos.","loading":"Cargando…","invalid_key":"Clave API ausente o inválida.","error":"Error: ","logout":"Salir","instruction":"Instrucción","response":"Respuesta final","trace":"Traza completa","tools":"Herramientas","status":"Estado"},
    "fr":{"title":"Audit des actions","subtitle":"Consultez les événements autonomes et les résultats faisant autorité.","login":"Connexion","api_key":"Clé API","intro":"La clé reste uniquement dans cet onglet.","search":"Rechercher","all":"Tous les modes","empty":"Aucun événement trouvé.","loading":"Chargement…","invalid_key":"Clé API absente ou invalide.","error":"Erreur : ","logout":"Déconnexion","instruction":"Instruction","response":"Réponse finale","trace":"Trace complète","tools":"Outils","status":"État"},
    "pt":{"title":"Auditoria de ações","subtitle":"Revise eventos autónomos e resultados oficiais das ferramentas.","login":"Entrar","api_key":"Chave API","intro":"A chave fica apenas nesta aba.","search":"Pesquisar eventos","all":"Todos os modos","empty":"Nenhum evento encontrado.","loading":"Carregando…","invalid_key":"Chave API ausente ou inválida.","error":"Erro: ","logout":"Sair","instruction":"Instrução","response":"Resposta final","trace":"Rastro completo","tools":"Ferramentas","status":"Estado"},
    "ar":{"title":"تدقيق الإجراءات","subtitle":"راجع الأحداث المستقلة ونتائج الأدوات الموثوقة.","login":"تسجيل الدخول","api_key":"مفتاح API","intro":"يبقى المفتاح في علامة التبويب هذه فقط.","search":"بحث في الأحداث","all":"كل الأوضاع","empty":"لا توجد أحداث.","loading":"جارٍ التحميل…","invalid_key":"مفتاح API مفقود أو غير صالح.","error":"خطأ: ","logout":"خروج","instruction":"التعليمات","response":"الرد النهائي","trace":"تتبع الأدوات الكامل","tools":"الأدوات","status":"الحالة"},
    "ja":{"title":"アクション監査","subtitle":"自動イベントと信頼できるツール結果を確認します。","login":"ログイン","api_key":"APIキー","intro":"キーはこのタブだけに保持されます。","search":"イベントを検索","all":"すべてのモード","empty":"イベントがありません。","loading":"読み込み中…","invalid_key":"APIキーがないか無効です。","error":"エラー: ","logout":"ログアウト","instruction":"指示","response":"最終回答","trace":"完全なツールトレース","tools":"ツール","status":"状態"},
    "ko":{"title":"작업 감사","subtitle":"자동 이벤트와 신뢰 가능한 도구 결과를 검토합니다.","login":"로그인","api_key":"API 키","intro":"키는 이 탭에만 보관됩니다.","search":"이벤트 검색","all":"모든 모드","empty":"이벤트가 없습니다.","loading":"불러오는 중…","invalid_key":"API 키가 없거나 올바르지 않습니다.","error":"오류: ","logout":"로그아웃","instruction":"지시","response":"최종 응답","trace":"전체 도구 추적","tools":"도구","status":"상태"},
    "zh":{"title":"操作审计","subtitle":"查看自主事件和权威工具结果。","login":"登录","api_key":"API 密钥","intro":"密钥仅保留在此标签页。","search":"搜索事件","all":"所有模式","empty":"没有事件。","loading":"加载中…","invalid_key":"API 密钥缺失或无效。","error":"错误：","logout":"退出","instruction":"指令","response":"最终响应","trace":"完整工具轨迹","tools":"工具","status":"状态"},
}
EXPORT_LABELS = {"en":"Export JSON","it":"Esporta JSON","de":"JSON exportieren","es":"Exportar JSON","fr":"Exporter JSON","pt":"Exportar JSON","ar":"تصدير JSON","ja":"JSONを書き出す","ko":"JSON 내보내기","zh":"导出 JSON"}
INSIGHT_LABELS = {
    "en":{"all_statuses":"All statuses","all_tools":"All tools","total":"Visible events","completed":"Completed","failed":"Failed"},
    "it":{"all_statuses":"Tutti gli stati","all_tools":"Tutti gli strumenti","total":"Eventi visibili","completed":"Completati","failed":"Falliti"},
    "de":{"all_statuses":"Alle Status","all_tools":"Alle Werkzeuge","total":"Sichtbare Ereignisse","completed":"Abgeschlossen","failed":"Fehlgeschlagen"},
    "es":{"all_statuses":"Todos los estados","all_tools":"Todas las herramientas","total":"Eventos visibles","completed":"Completados","failed":"Fallidos"},
    "fr":{"all_statuses":"Tous les états","all_tools":"Tous les outils","total":"Événements visibles","completed":"Terminés","failed":"Échoués"},
    "pt":{"all_statuses":"Todos os estados","all_tools":"Todas as ferramentas","total":"Eventos visíveis","completed":"Concluídos","failed":"Falhados"},
    "ar":{"all_statuses":"كل الحالات","all_tools":"كل الأدوات","total":"الأحداث الظاهرة","completed":"مكتملة","failed":"فاشلة"},
    "ja":{"all_statuses":"すべての状態","all_tools":"すべてのツール","total":"表示イベント","completed":"完了","failed":"失敗"},
    "ko":{"all_statuses":"모든 상태","all_tools":"모든 도구","total":"표시 이벤트","completed":"완료","failed":"실패"},
    "zh":{"all_statuses":"所有状态","all_tools":"所有工具","total":"可见事件","completed":"已完成","failed":"失败"},
}

PIPELINE_LABELS = {
    "en": {"requested":"Requested","validation":"Validation","ha_call":"Home Assistant call","outcome":"Outcome","not_called":"Not called"},
    "it": {"requested":"Richiesta","validation":"Validazione","ha_call":"Chiamata Home Assistant","outcome":"Esito","not_called":"Non effettuata"},
    "de": {"requested":"Angefordert","validation":"Validierung","ha_call":"Home-Assistant-Aufruf","outcome":"Ergebnis","not_called":"Nicht ausgeführt"},
    "es": {"requested":"Solicitado","validation":"Validación","ha_call":"Llamada a Home Assistant","outcome":"Resultado","not_called":"No realizada"},
    "fr": {"requested":"Demandé","validation":"Validation","ha_call":"Appel Home Assistant","outcome":"Résultat","not_called":"Non effectué"},
    "pt": {"requested":"Solicitado","validation":"Validação","ha_call":"Chamada Home Assistant","outcome":"Resultado","not_called":"Não efetuada"},
    "ar": {"requested":"المطلوب","validation":"التحقق","ha_call":"استدعاء Home Assistant","outcome":"النتيجة","not_called":"لم يتم"},
    "ja": {"requested":"要求","validation":"検証","ha_call":"Home Assistant 呼び出し","outcome":"結果","not_called":"未実行"},
    "ko": {"requested":"요청","validation":"검증","ha_call":"Home Assistant 호출","outcome":"결과","not_called":"호출 안 함"},
    "zh": {"requested":"请求","validation":"验证","ha_call":"Home Assistant 调用","outcome":"结果","not_called":"未调用"},
}

HTML = """<!doctype html><html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__ · House Brain</title><style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#151d33;--line:#2b385a;--text:#eef2ff;--muted:#a8b3cf;--accent:#75a7ff;--ok:#6ed6a0;--bad:#ff7f8f}*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#080d19,#111a31);color:var(--text);font:15px system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:28px 18px 60px}header,.toolbar{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}h1{margin:0}p,.meta{color:var(--muted)}.panel,.card{background:rgba(21,29,51,.94);border:1px solid var(--line);border-radius:14px;padding:16px}.panel{margin-bottom:16px}.list{display:grid;gap:12px}input,select,button{font:inherit;color:var(--text);background:#0d1428;border:1px solid var(--line);border-radius:9px;padding:10px}input{flex:1;min-width:220px}button{cursor:pointer}.hidden{display:none}.status{min-height:22px;color:var(--muted)}.error{color:var(--bad)}.badge{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;margin-right:6px}.executed{color:var(--ok)}.rejected,.failed{color:var(--bad)}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0d1428;padding:12px;border-radius:9px}details{margin-top:10px}summary{cursor:pointer;color:var(--accent)}.insights{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:14px}.insight{background:#0d1428;border:1px solid var(--line);border-radius:12px;padding:12px}.insight strong{display:block;font-size:1.5rem;color:var(--accent)}.audit-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.audit-stage{padding:10px;border-left:3px solid var(--accent);background:#0d1428;border-radius:8px;overflow-wrap:anywhere}.audit-stage strong{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}@media(max-width:650px){.insights,.audit-flow{grid-template-columns:1fr}}
</style></head><body><main><header><div><h1>__TITLE__</h1><p>__SUBTITLE__</p></div><button id="logout" class="hidden">__LOGOUT__</button></header>
<section id="auth" class="panel"><form id="authForm"><p>__INTRO__</p><input id="apiKey" type="password" autocomplete="current-password" placeholder="__API_KEY__" required> <button>__LOGIN__</button><div id="authError" class="status error"></div></form></section>
<section id="app" class="hidden"><div class="panel"><div id="insights" class="insights"></div><div class="toolbar"><input id="search" type="search" placeholder="__SEARCH__"><select id="mode"><option value="">__ALL__</option><option>observe</option><option>simulate</option><option>execute</option></select><select id="eventStatus"><option value="">__ALL_STATUSES__</option><option>completed</option><option>failed</option></select><select id="tool"><option value="">__ALL_TOOLS__</option></select><button id="export">__EXPORT__</button><button id="refresh">↻</button></div><div id="status" class="status"></div></div><div id="list" class="list"></div></section>
<script>(()=>{"use strict";const i18n=__I18N__,KEY="house_brain_api_key";let items=[];const $=id=>document.getElementById(id),apiKey=()=>(sessionStorage.getItem(KEY)||"").trim();
async function api(path){return fetch(path,{headers:{"X-API-Key":apiKey(),"Accept":"application/json"}})}async function payload(response){const text=await response.text();if(!text)return{};try{return JSON.parse(text)}catch(error){throw new Error(response.ok?response.statusText:text.slice(0,300))}}function message(text,error=false){$("status").textContent=text;$("status").className="status"+(error?" error":"")}function loginError(error){sessionStorage.removeItem(KEY);$("authError").textContent=i18n.error+(error?.message||String(error));$("auth").classList.remove("hidden");$("app").classList.add("hidden");$("logout").classList.add("hidden")}
function labeled(label,value){const box=document.createElement("div"),strong=document.createElement("strong");strong.textContent=label+": ";box.append(strong,document.createTextNode(value||"—"));return box}
function pipeline(item){const trace=item.tool_trace||[],actions=trace.filter(record=>["perform_action","perform_actions"].includes(record.tool)),requested=actions.length?actions.map(record=>{const args=record.arguments||{},service=[args.domain,args.service].filter(Boolean).join(".");return(args.entity_id||"unknown")+": "+(service||record.tool)}).join("\n"):"—",validation=actions.length?actions.map(record=>record.error?record.status+": "+record.error:record.status).join("\n"):"—",haCall=actions.some(record=>record.outcome==="executed")?"executed":i18n.not_called,outcome=actions.length?actions.map(record=>record.outcome||record.status).join("\n"):(item.status||"—"),flow=document.createElement("div");flow.className="audit-flow";for(const [label,value] of [[i18n.requested,requested],[i18n.validation,validation],[i18n.ha_call,haCall],[i18n.outcome,outcome]]){const stage=document.createElement("div"),heading=document.createElement("strong"),body=document.createElement("span");stage.className="audit-stage";heading.textContent=label;body.textContent=value;stage.append(heading,body);flow.append(stage)}return flow}
function filtered(){const q=$("search").value.trim().toLocaleLowerCase(),mode=$("mode").value,eventStatus=$("eventStatus").value,tool=$("tool").value;return items.filter(x=>(!mode||x.mode===mode)&&(!eventStatus||x.status===eventStatus)&&(!tool||(x.tools_used||[]).includes(tool))&&JSON.stringify(x).toLocaleLowerCase().includes(q))}function insight(label,value){const box=document.createElement("div"),strong=document.createElement("strong"),span=document.createElement("span");box.className="insight";strong.textContent=String(value);span.textContent=label;box.append(strong,span);return box}function render(){const shown=filtered(),completed=shown.filter(x=>x.status==="completed").length;$("insights").replaceChildren(insight(i18n.total,shown.length),insight(i18n.completed,completed),insight(i18n.failed,shown.length-completed));$("list").replaceChildren();if(!shown.length){const e=document.createElement("div");e.className="panel";e.textContent=i18n.empty;$("list").append(e);return}for(const item of shown){const card=document.createElement("article");card.className="card";const title=document.createElement("h3");title.textContent=item.event_type+" · "+new Date(item.created_at).toLocaleString();const meta=document.createElement("div");meta.className="meta";for(const value of [item.mode,item.status]){const badge=document.createElement("span");badge.className="badge "+value;badge.textContent=value;meta.append(badge)}const instruction=labeled(i18n.instruction,item.instruction),response=labeled(i18n.response,item.response),tools=labeled(i18n.tools,(item.tools_used||[]).join(", "));const details=document.createElement("details"),summary=document.createElement("summary"),pre=document.createElement("pre");summary.textContent=i18n.trace;pre.textContent=JSON.stringify(item.tool_trace||[],null,2);details.append(summary,pre);card.append(title,meta,instruction,response,tools,pipeline(item),details);$("list").append(card)}}
async function load(){message(i18n.loading);const response=await api("/events?limit=100");const body=await payload(response);if(response.status===401||response.status===403)throw new Error(i18n.invalid_key);if(!response.ok)throw new Error(body.detail||response.statusText);if(!Array.isArray(body))throw new Error(response.statusText);items=body;const selected=$("tool").value,tools=[...new Set(items.flatMap(x=>x.tools_used||[]))].sort();$("tool").replaceChildren();const all=document.createElement("option");all.value="";all.textContent=i18n.all_tools;$("tool").append(all);for(const name of tools){const option=document.createElement("option");option.value=name;option.textContent=name;$("tool").append(option)}if(tools.includes(selected))$("tool").value=selected;render();message("");$("auth").classList.add("hidden");$("app").classList.remove("hidden");$("logout").classList.remove("hidden")}
function guard(fn){return async(...args)=>{try{await fn(...args)}catch(error){message(i18n.error+(error?.message||String(error)),true)}}}$("authForm").onsubmit=async event=>{event.preventDefault();$("authError").textContent="";const key=$("apiKey").value.trim();if(!key){loginError(new Error(i18n.invalid_key));return}sessionStorage.setItem(KEY,key);try{await load()}catch(error){loginError(error)}};$("search").oninput=render;$("mode").onchange=render;$("eventStatus").onchange=render;$("tool").onchange=render;$("refresh").onclick=guard(load);$("export").onclick=()=>{const blob=new Blob([JSON.stringify(filtered(),null,2)],{type:"application/json"}),link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="house-brain-audit.json";link.click();URL.revokeObjectURL(link.href)};$("logout").onclick=()=>{sessionStorage.removeItem(KEY);location.reload()};if(apiKey())load().catch(loginError)})();</script></main></body></html>"""


def audit_page(
    language: str,
    frame_ancestor: str | None = None,
) -> HTMLResponse:
    family = language_family(language)
    messages = {
        **MESSAGES.get(family, MESSAGES["en"]),
        "export": EXPORT_LABELS.get(family, EXPORT_LABELS["en"]),
        **INSIGHT_LABELS.get(family, INSIGHT_LABELS["en"]),
        **PIPELINE_LABELS.get(family, PIPELINE_LABELS["en"]),
    }
    replacements = {
        "__LANG__": family,
        "__I18N__": json.dumps(messages, ensure_ascii=True).replace("<", "\\u003c"),
        **{f"__{key.upper()}__": value for key, value in messages.items()},
    }
    html = HTML
    html = html.replace("</style>", f"{SHARED_THEME_CSS}</style>", 1)
    html = html.replace(
        "<body>",
        f'<body class="hb-audit">{shared_navigation("audit", language)}',
        1,
    )
    for token, value in replacements.items():
        html = html.replace(token, value)
    return HTMLResponse(
        html,
        headers=browser_security_headers(frame_ancestor),
    )
