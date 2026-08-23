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
    "en":{"title":"System diagnostics","subtitle":"Check House Brain dependencies and persistent data from one safe report.","login":"Sign in","api_key":"API key","intro":"The key stays only in this browser tab.","loading":"Loading…","invalid_key":"Missing or invalid API key.","error":"Error: ","logout":"Sign out","refresh":"Refresh","download":"Download report","overall":"Overall status","home_assistant":"Home Assistant","llm":"LLM provider","persistence":"Persistence","ok":"Operational","degraded":"Needs attention"},
    "it":{"title":"Diagnostica di sistema","subtitle":"Controlla dipendenze e dati persistenti di House Brain in un unico rapporto sicuro.","login":"Accedi","api_key":"Chiave API","intro":"La chiave rimane soltanto nella sessione di questa scheda.","loading":"Caricamento…","invalid_key":"Chiave API mancante o non valida.","error":"Errore: ","logout":"Esci","refresh":"Aggiorna","download":"Scarica rapporto","overall":"Stato generale","home_assistant":"Home Assistant","llm":"Provider LLM","persistence":"Persistenza","ok":"Operativo","degraded":"Richiede attenzione"},
    "de":{"title":"Systemdiagnose","subtitle":"Abhängigkeiten und persistente Daten in einem sicheren Bericht prüfen.","login":"Anmelden","api_key":"API-Schlüssel","intro":"Der Schlüssel bleibt nur in diesem Tab.","loading":"Laden…","invalid_key":"API-Schlüssel fehlt oder ist ungültig.","error":"Fehler: ","logout":"Abmelden","refresh":"Aktualisieren","download":"Bericht laden","overall":"Gesamtstatus","home_assistant":"Home Assistant","llm":"LLM-Anbieter","persistence":"Persistenz","ok":"Betriebsbereit","degraded":"Prüfung erforderlich"},
    "es":{"title":"Diagnóstico del sistema","subtitle":"Comprueba dependencias y datos persistentes en un informe seguro.","login":"Acceder","api_key":"Clave API","intro":"La clave permanece solo en esta pestaña.","loading":"Cargando…","invalid_key":"Clave API ausente o inválida.","error":"Error: ","logout":"Salir","refresh":"Actualizar","download":"Descargar informe","overall":"Estado general","home_assistant":"Home Assistant","llm":"Proveedor LLM","persistence":"Persistencia","ok":"Operativo","degraded":"Requiere atención"},
    "fr":{"title":"Diagnostic système","subtitle":"Contrôlez les dépendances et données persistantes dans un rapport sûr.","login":"Connexion","api_key":"Clé API","intro":"La clé reste uniquement dans cet onglet.","loading":"Chargement…","invalid_key":"Clé API absente ou invalide.","error":"Erreur : ","logout":"Déconnexion","refresh":"Actualiser","download":"Télécharger","overall":"État général","home_assistant":"Home Assistant","llm":"Fournisseur LLM","persistence":"Persistance","ok":"Opérationnel","degraded":"Attention requise"},
    "pt":{"title":"Diagnóstico do sistema","subtitle":"Verifique dependências e dados persistentes num relatório seguro.","login":"Entrar","api_key":"Chave API","intro":"A chave fica apenas nesta aba.","loading":"Carregando…","invalid_key":"Chave API ausente ou inválida.","error":"Erro: ","logout":"Sair","refresh":"Atualizar","download":"Baixar relatório","overall":"Estado geral","home_assistant":"Home Assistant","llm":"Fornecedor LLM","persistence":"Persistência","ok":"Operacional","degraded":"Requer atenção"},
    "ar":{"title":"تشخيص النظام","subtitle":"تحقق من التبعيات والبيانات الدائمة في تقرير آمن.","login":"تسجيل الدخول","api_key":"مفتاح API","intro":"يبقى المفتاح في علامة التبويب هذه فقط.","loading":"جارٍ التحميل…","invalid_key":"مفتاح API مفقود أو غير صالح.","error":"خطأ: ","logout":"خروج","refresh":"تحديث","download":"تنزيل التقرير","overall":"الحالة العامة","home_assistant":"Home Assistant","llm":"مزود LLM","persistence":"التخزين الدائم","ok":"يعمل","degraded":"يحتاج إلى اهتمام"},
    "ja":{"title":"システム診断","subtitle":"依存関係と永続データを安全なレポートで確認します。","login":"ログイン","api_key":"APIキー","intro":"キーはこのタブだけに保持されます。","loading":"読み込み中…","invalid_key":"APIキーがないか無効です。","error":"エラー: ","logout":"ログアウト","refresh":"更新","download":"レポートを保存","overall":"全体の状態","home_assistant":"Home Assistant","llm":"LLMプロバイダー","persistence":"永続化","ok":"正常","degraded":"要確認"},
    "ko":{"title":"시스템 진단","subtitle":"종속성과 영구 데이터를 안전한 보고서로 확인합니다.","login":"로그인","api_key":"API 키","intro":"키는 이 탭에만 보관됩니다.","loading":"불러오는 중…","invalid_key":"API 키가 없거나 올바르지 않습니다.","error":"오류: ","logout":"로그아웃","refresh":"새로 고침","download":"보고서 다운로드","overall":"전체 상태","home_assistant":"Home Assistant","llm":"LLM 공급자","persistence":"영구 저장소","ok":"정상","degraded":"확인 필요"},
    "zh":{"title":"系统诊断","subtitle":"通过安全报告检查依赖项和持久数据。","login":"登录","api_key":"API 密钥","intro":"密钥仅保留在此标签页。","loading":"加载中…","invalid_key":"API 密钥缺失或无效。","error":"错误：","logout":"退出","refresh":"刷新","download":"下载报告","overall":"总体状态","home_assistant":"Home Assistant","llm":"LLM 提供商","persistence":"持久化","ok":"正常","degraded":"需要注意"},
}

GUIDANCE = {
    "en":{"checks":"Suggested checks","home_assistant_help":"Verify the Home Assistant URL, token, and network access from the House Brain container.","llm_help":"Verify the provider URL, that the configured model is loaded, and the API key when required.","persistence_help":"Verify that /config is writable and that the policy, database, and backup directory are accessible."},
    "it":{"checks":"Controlli suggeriti","home_assistant_help":"Verifica URL e token di Home Assistant e la raggiungibilità dal container House Brain.","llm_help":"Verifica l'URL del provider, che il modello configurato sia caricato e la chiave API quando richiesta.","persistence_help":"Verifica che /config sia scrivibile e che policy, database e cartella dei backup siano accessibili."},
    "de":{"checks":"Empfohlene Prüfungen","home_assistant_help":"Home-Assistant-URL, Token und Netzwerkzugriff aus dem House-Brain-Container prüfen.","llm_help":"Anbieter-URL, geladenes konfiguriertes Modell und gegebenenfalls API-Schlüssel prüfen.","persistence_help":"Prüfen, ob /config beschreibbar ist und Richtlinie, Datenbank und Sicherungsordner erreichbar sind."},
    "es":{"checks":"Comprobaciones sugeridas","home_assistant_help":"Comprueba la URL y el token de Home Assistant y el acceso desde el contenedor House Brain.","llm_help":"Comprueba la URL del proveedor, que el modelo configurado esté cargado y la clave API cuando sea necesaria.","persistence_help":"Comprueba que /config sea escribible y que la política, la base de datos y la carpeta de copias sean accesibles."},
    "fr":{"checks":"Contrôles suggérés","home_assistant_help":"Vérifiez l'URL et le jeton Home Assistant ainsi que l'accès depuis le conteneur House Brain.","llm_help":"Vérifiez l'URL du fournisseur, le chargement du modèle configuré et la clé API si nécessaire.","persistence_help":"Vérifiez que /config est accessible en écriture et que la politique, la base et le dossier de sauvegarde sont accessibles."},
    "pt":{"checks":"Verificações sugeridas","home_assistant_help":"Verifique o URL e token do Home Assistant e o acesso a partir do contentor House Brain.","llm_help":"Verifique o URL do fornecedor, se o modelo configurado está carregado e a chave API quando necessária.","persistence_help":"Verifique se /config permite escrita e se a política, a base de dados e a pasta de backups estão acessíveis."},
    "ar":{"checks":"فحوص مقترحة","home_assistant_help":"تحقق من عنوان Home Assistant والرمز وإمكانية الوصول من حاوية House Brain.","llm_help":"تحقق من عنوان المزود وتحميل النموذج المضبوط ومفتاح API عند الحاجة.","persistence_help":"تحقق من إمكانية الكتابة في /config والوصول إلى السياسة وقاعدة البيانات ومجلد النسخ الاحتياطية."},
    "ja":{"checks":"推奨確認事項","home_assistant_help":"Home Assistant のURLとトークン、および House Brain コンテナからの接続を確認してください。","llm_help":"プロバイダーURL、設定モデルの読み込み、必要な場合はAPIキーを確認してください。","persistence_help":"/config が書き込み可能で、ポリシー、データベース、バックアップフォルダーにアクセスできることを確認してください。"},
    "ko":{"checks":"권장 확인 사항","home_assistant_help":"Home Assistant URL과 토큰, House Brain 컨테이너에서의 연결을 확인하세요.","llm_help":"공급자 URL, 설정 모델의 로드 상태와 필요한 경우 API 키를 확인하세요.","persistence_help":"/config 쓰기 권한과 정책, 데이터베이스, 백업 폴더 접근을 확인하세요."},
    "zh":{"checks":"建议检查","home_assistant_help":"检查 Home Assistant URL、令牌以及 House Brain 容器的网络访问。","llm_help":"检查提供商 URL、配置的模型是否已加载，以及需要时的 API 密钥。","persistence_help":"检查 /config 是否可写，以及策略、数据库和备份目录是否可访问。"},
}

HTML = """<!doctype html><html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__ · House Brain</title><style>*{box-sizing:border-box}body{margin:0}main{max-width:1120px;margin:auto;padding:28px 18px 60px}header,.toolbar{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}h1{margin:0}.panel{border:1px solid;padding:18px;margin-bottom:16px}.hidden{display:none}.status{min-height:22px}.error{color:var(--hb-red)}.summary{display:flex;gap:14px;align-items:center}.dot{width:14px;height:14px;border-radius:50%;background:var(--hb-green);box-shadow:0 0 22px currentColor}.degraded .dot,.error-card .dot{background:var(--hb-red)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}.component pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--hb-surface-deep);border-radius:12px;padding:14px;color:var(--hb-muted)}button{cursor:pointer}</style></head><body><main><header><div><h1>__TITLE__</h1><p>__SUBTITLE__</p></div><button id="logout" class="hidden">__LOGOUT__</button></header><section id="auth" class="panel"><form id="authForm"><p>__INTRO__</p><input id="apiKey" type="password" autocomplete="current-password" placeholder="__API_KEY__" required> <button>__LOGIN__</button><div id="authError" class="status error"></div></form></section><section id="app" class="hidden"><div class="panel"><div class="toolbar"><div id="summary" class="summary"><span class="dot"></span><strong id="overall"></strong></div><div><button id="refresh">__REFRESH__</button> <button id="download">__DOWNLOAD__</button></div></div><div id="status" class="status"></div></div><div id="grid" class="grid"></div></section><script>(()=>{"use strict";const i18n=__I18N__,KEY="house_brain_api_key";let report=null;const $=id=>document.getElementById(id),apiKey=()=>sessionStorage.getItem(KEY)||"";function message(text,error=false){$("status").textContent=text;$("status").className="status"+(error?" error":"")}function card(title,data){const article=document.createElement("article"),heading=document.createElement("h2"),pre=document.createElement("pre");article.className="panel component"+(data.status==="error"?" error-card":"");heading.textContent=title;pre.textContent=JSON.stringify(data,null,2);article.append(heading,pre);return article}function render(){const healthy=report.status==="ok";$("summary").className="summary"+(healthy?"":" degraded");$("overall").textContent=i18n.overall+": "+(healthy?i18n.ok:i18n.degraded);$("grid").replaceChildren(card(i18n.home_assistant,report.home_assistant),card(i18n.llm,report.llm),card(i18n.persistence,report.persistence))}async function body(response){const text=await response.text();try{return JSON.parse(text)}catch{return{detail:text}}}async function load(){message(i18n.loading);const response=await fetch("/diagnostics",{headers:{"X-API-Key":apiKey()}}),data=await body(response);if(response.status===401)throw new Error(i18n.invalid_key);if(!response.ok)throw new Error(data.detail||response.statusText);report=data;render();message("");$("auth").classList.add("hidden");$("app").classList.remove("hidden");$("logout").classList.remove("hidden")}function guard(fn){return async(...args)=>{try{await fn(...args)}catch(error){message(i18n.error+error.message,true)}}}$("authForm").onsubmit=guard(async event=>{event.preventDefault();sessionStorage.setItem(KEY,$("apiKey").value);await load()});$("refresh").onclick=guard(load);$("download").onclick=()=>{if(!report)return;const blob=new Blob([JSON.stringify(report,null,2)],{type:"application/json"}),link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download="house-brain-diagnostics.json";link.click();URL.revokeObjectURL(link.href)};$("logout").onclick=()=>{sessionStorage.removeItem(KEY);location.reload()};if(apiKey())load().catch(error=>{sessionStorage.removeItem(KEY);$("authError").textContent=error.message})})();</script></main></body></html>"""


HTML = HTML.replace(
    "button{cursor:pointer}</style>",
    ".guidance{border-left:3px solid var(--hb-red);padding:10px 12px;"
    "background:var(--hb-surface-deep);border-radius:8px}.guidance strong{"
    "display:block;margin-bottom:5px}button{cursor:pointer}</style>",
)
HTML = HTML.replace(
    'function card(title,data){const article=document.createElement("article"),'
    'heading=document.createElement("h2"),pre=document.createElement("pre");'
    'article.className="panel component"+(data.status==="error"?" error-card":"");'
    'heading.textContent=title;pre.textContent=JSON.stringify(data,null,2);'
    'article.append(heading,pre);return article}',
    'function card(title,data,help){const article=document.createElement("article"),'
    'heading=document.createElement("h2"),pre=document.createElement("pre");'
    'article.className="panel component"+(data.status==="error"?" error-card":"");'
    'heading.textContent=title;article.append(heading);if(data.status==="error"){'
    'const guidance=document.createElement("div"),label=document.createElement("strong");'
    'guidance.className="guidance";label.textContent=i18n.checks;'
    'guidance.append(label,document.createTextNode(help));article.append(guidance)}'
    'pre.textContent=JSON.stringify(data,null,2);article.append(pre);return article}',
)
HTML = HTML.replace(
    'card(i18n.home_assistant,report.home_assistant),'
    'card(i18n.llm,report.llm),card(i18n.persistence,report.persistence)',
    'card(i18n.home_assistant,report.home_assistant,i18n.home_assistant_help),'
    'card(i18n.llm,report.llm,i18n.llm_help),'
    'card(i18n.persistence,report.persistence,i18n.persistence_help)',
)


def diagnostics_page(
    language: str,
    frame_ancestor: str | None = None,
) -> HTMLResponse:
    family = language_family(language)
    messages = {
        **MESSAGES.get(family, MESSAGES["en"]),
        **GUIDANCE.get(family, GUIDANCE["en"]),
    }
    html = HTML.replace("</style>", f"{SHARED_THEME_CSS}</style>", 1)
    html = html.replace("<body>", f'<body class="hb-diagnostics">{shared_navigation("diagnostics", language)}', 1)
    replacements = {"__LANG__": family, "__I18N__": json.dumps(messages, ensure_ascii=True).replace("<", "\\u003c"), **{f"__{key.upper()}__": value for key, value in messages.items()}}
    for token, value in replacements.items():
        html = html.replace(token, value)
    return HTMLResponse(html, headers=browser_security_headers(frame_ancestor))
