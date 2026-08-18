# ruff: noqa: E501
import json

from fastapi.responses import HTMLResponse

from house_brain.languages import language_family

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

HTML = """<!doctype html><html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__ · House Brain</title><style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#151d33;--line:#2b385a;--text:#eef2ff;--muted:#a8b3cf;--accent:#75a7ff;--ok:#6ed6a0;--bad:#ff7f8f}*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#080d19,#111a31);color:var(--text);font:15px system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:28px 18px 60px}header,.toolbar{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}h1{margin:0}p,.meta{color:var(--muted)}.panel,.card{background:rgba(21,29,51,.94);border:1px solid var(--line);border-radius:14px;padding:16px}.panel{margin-bottom:16px}.list{display:grid;gap:12px}input,select,button{font:inherit;color:var(--text);background:#0d1428;border:1px solid var(--line);border-radius:9px;padding:10px}input{flex:1;min-width:220px}button{cursor:pointer}.hidden{display:none}.status{min-height:22px;color:var(--muted)}.error{color:var(--bad)}.badge{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 8px;margin-right:6px}.executed{color:var(--ok)}.rejected,.failed{color:var(--bad)}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0d1428;padding:12px;border-radius:9px}details{margin-top:10px}summary{cursor:pointer;color:var(--accent)}
</style></head><body><main><header><div><h1>__TITLE__</h1><p>__SUBTITLE__</p></div><button id="logout" class="hidden">__LOGOUT__</button></header>
<section id="auth" class="panel"><form id="authForm"><p>__INTRO__</p><input id="apiKey" type="password" autocomplete="current-password" placeholder="__API_KEY__" required> <button>__LOGIN__</button><div id="authError" class="status error"></div></form></section>
<section id="app" class="hidden"><div class="panel"><div class="toolbar"><input id="search" type="search" placeholder="__SEARCH__"><select id="mode"><option value="">__ALL__</option><option>observe</option><option>simulate</option><option>execute</option></select><button id="refresh">↻</button></div><div id="status" class="status"></div></div><div id="list" class="list"></div></section>
<script>(()=>{"use strict";const i18n=__I18N__,KEY="house_brain_api_key";let items=[];const $=id=>document.getElementById(id),apiKey=()=>sessionStorage.getItem(KEY)||"";
async function api(path){return fetch(path,{headers:{"X-API-Key":apiKey()}})}function message(text,error=false){$("status").textContent=text;$("status").className="status"+(error?" error":"")}
function labeled(label,value){const box=document.createElement("div"),strong=document.createElement("strong");strong.textContent=label+": ";box.append(strong,document.createTextNode(value||"—"));return box}
function render(){const q=$("search").value.trim().toLocaleLowerCase(),mode=$("mode").value;const shown=items.filter(x=>(!mode||x.mode===mode)&&JSON.stringify(x).toLocaleLowerCase().includes(q));$("list").replaceChildren();if(!shown.length){const e=document.createElement("div");e.className="panel";e.textContent=i18n.empty;$("list").append(e);return}for(const item of shown){const card=document.createElement("article");card.className="card";const title=document.createElement("h3");title.textContent=item.event_type+" · "+new Date(item.created_at).toLocaleString();const meta=document.createElement("div");meta.className="meta";for(const value of [item.mode,item.status]){const badge=document.createElement("span");badge.className="badge "+value;badge.textContent=value;meta.append(badge)}const instruction=labeled(i18n.instruction,item.instruction),response=labeled(i18n.response,item.response),tools=labeled(i18n.tools,(item.tools_used||[]).join(", "));const details=document.createElement("details"),summary=document.createElement("summary"),pre=document.createElement("pre");summary.textContent=i18n.trace;pre.textContent=JSON.stringify(item.tool_trace||[],null,2);details.append(summary,pre);card.append(title,meta,instruction,response,tools,details);$("list").append(card)}}
async function load(){message(i18n.loading);const response=await api("/events?limit=100");if(response.status===401)throw new Error(i18n.invalid_key);const body=await response.json();if(!response.ok)throw new Error(body.detail||response.statusText);items=body;render();message("");$("auth").classList.add("hidden");$("app").classList.remove("hidden");$("logout").classList.remove("hidden")}
function guard(fn){return async(...args)=>{try{await fn(...args)}catch(error){message(i18n.error+error.message,true)}}}$("authForm").onsubmit=guard(async event=>{event.preventDefault();sessionStorage.setItem(KEY,$("apiKey").value);await load()});$("search").oninput=render;$("mode").onchange=render;$("refresh").onclick=guard(load);$("logout").onclick=()=>{sessionStorage.removeItem(KEY);location.reload()};if(apiKey())load().catch(error=>{sessionStorage.removeItem(KEY);$("authError").textContent=error.message})})();</script></main></body></html>"""


def audit_page(language: str) -> HTMLResponse:
    family = language_family(language)
    messages = MESSAGES.get(family, MESSAGES["en"])
    replacements = {
        "__LANG__": family,
        "__I18N__": json.dumps(messages, ensure_ascii=True).replace("<", "\\u003c"),
        **{f"__{key.upper()}__": value for key, value in messages.items()},
    }
    html = HTML
    for token, value in replacements.items():
        html = html.replace(token, value)
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; connect-src 'self'; "
                "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )
