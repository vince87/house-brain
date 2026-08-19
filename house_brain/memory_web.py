# ruff: noqa: E501
import json

from fastapi.responses import HTMLResponse

from house_brain.languages import language_family
from house_brain.web_theme import SHARED_THEME_CSS

MESSAGES = {
    "en": {"title":"Memory manager","subtitle":"View and edit persistent memories.","login":"Sign in","api_key":"API key","intro":"The key stays only in this browser tab.","active":"Active","trash":"Trash","new":"New memory","search":"Search memories","key":"Key","value":"Value","category":"Category","importance":"Importance","save":"Save","cancel":"Cancel","edit":"Edit","delete":"Move to trash","restore":"Restore","empty":"No memories found.","loading":"Loading…","saved":"Memory saved.","deleted":"Memory moved to trash.","restored":"Memory restored.","confirm_delete":"Move this memory to the recoverable trash?","invalid_key":"Missing or invalid API key.","error":"Error: ","logout":"Sign out"},
    "it": {"title":"Gestione memorie","subtitle":"Visualizza e modifica le memorie persistenti.","login":"Accedi","api_key":"Chiave API","intro":"La chiave rimane soltanto nella sessione di questa scheda.","active":"Attive","trash":"Cestino","new":"Nuova memoria","search":"Cerca memorie","key":"Chiave","value":"Valore","category":"Categoria","importance":"Importanza","save":"Salva","cancel":"Annulla","edit":"Modifica","delete":"Sposta nel cestino","restore":"Ripristina","empty":"Nessuna memoria trovata.","loading":"Caricamento…","saved":"Memoria salvata.","deleted":"Memoria spostata nel cestino.","restored":"Memoria ripristinata.","confirm_delete":"Spostare questa memoria nel cestino recuperabile?","invalid_key":"Chiave API mancante o non valida.","error":"Errore: ","logout":"Esci"},
    "de": {"title":"Speicherverwaltung","subtitle":"Persistente Erinnerungen anzeigen und bearbeiten.","login":"Anmelden","api_key":"API-Schlüssel","intro":"Der Schlüssel bleibt nur in diesem Tab.","active":"Aktiv","trash":"Papierkorb","new":"Neue Erinnerung","search":"Erinnerungen suchen","key":"Schlüssel","value":"Wert","category":"Kategorie","importance":"Wichtigkeit","save":"Speichern","cancel":"Abbrechen","edit":"Bearbeiten","delete":"In Papierkorb","restore":"Wiederherstellen","empty":"Keine Erinnerungen gefunden.","loading":"Laden…","saved":"Erinnerung gespeichert.","deleted":"Erinnerung verschoben.","restored":"Erinnerung wiederhergestellt.","confirm_delete":"Diese Erinnerung in den Papierkorb verschieben?","invalid_key":"API-Schlüssel fehlt oder ist ungültig.","error":"Fehler: ","logout":"Abmelden"},
    "es": {"title":"Gestión de memorias","subtitle":"Consulta y edita memorias persistentes.","login":"Acceder","api_key":"Clave API","intro":"La clave permanece solo en esta pestaña.","active":"Activas","trash":"Papelera","new":"Nueva memoria","search":"Buscar memorias","key":"Clave","value":"Valor","category":"Categoría","importance":"Importancia","save":"Guardar","cancel":"Cancelar","edit":"Editar","delete":"Mover a papelera","restore":"Restaurar","empty":"No se encontraron memorias.","loading":"Cargando…","saved":"Memoria guardada.","deleted":"Memoria movida.","restored":"Memoria restaurada.","confirm_delete":"¿Mover esta memoria a la papelera recuperable?","invalid_key":"Clave API ausente o inválida.","error":"Error: ","logout":"Salir"},
    "fr": {"title":"Gestion des mémoires","subtitle":"Afficher et modifier les mémoires persistantes.","login":"Connexion","api_key":"Clé API","intro":"La clé reste uniquement dans cet onglet.","active":"Actives","trash":"Corbeille","new":"Nouvelle mémoire","search":"Rechercher","key":"Clé","value":"Valeur","category":"Catégorie","importance":"Importance","save":"Enregistrer","cancel":"Annuler","edit":"Modifier","delete":"Mettre à la corbeille","restore":"Restaurer","empty":"Aucune mémoire trouvée.","loading":"Chargement…","saved":"Mémoire enregistrée.","deleted":"Mémoire déplacée.","restored":"Mémoire restaurée.","confirm_delete":"Mettre cette mémoire dans la corbeille récupérable ?","invalid_key":"Clé API absente ou invalide.","error":"Erreur : ","logout":"Déconnexion"},
    "pt": {"title":"Gestão de memórias","subtitle":"Veja e edite memórias persistentes.","login":"Entrar","api_key":"Chave API","intro":"A chave fica apenas nesta aba.","active":"Ativas","trash":"Lixeira","new":"Nova memória","search":"Pesquisar memórias","key":"Chave","value":"Valor","category":"Categoria","importance":"Importância","save":"Salvar","cancel":"Cancelar","edit":"Editar","delete":"Mover para lixeira","restore":"Restaurar","empty":"Nenhuma memória encontrada.","loading":"Carregando…","saved":"Memória salva.","deleted":"Memória movida.","restored":"Memória restaurada.","confirm_delete":"Mover esta memória para a lixeira recuperável?","invalid_key":"Chave API ausente ou inválida.","error":"Erro: ","logout":"Sair"},
    "ar": {"title":"إدارة الذاكرة","subtitle":"عرض الذكريات الدائمة وتعديلها.","login":"تسجيل الدخول","api_key":"مفتاح API","intro":"يبقى المفتاح في علامة التبويب هذه فقط.","active":"نشطة","trash":"المهملات","new":"ذاكرة جديدة","search":"بحث","key":"المفتاح","value":"القيمة","category":"الفئة","importance":"الأهمية","save":"حفظ","cancel":"إلغاء","edit":"تعديل","delete":"نقل إلى المهملات","restore":"استعادة","empty":"لا توجد ذكريات.","loading":"جارٍ التحميل…","saved":"تم الحفظ.","deleted":"تم النقل إلى المهملات.","restored":"تمت الاستعادة.","confirm_delete":"نقل هذه الذاكرة إلى المهملات؟","invalid_key":"مفتاح API مفقود أو غير صالح.","error":"خطأ: ","logout":"خروج"},
    "ja": {"title":"メモリ管理","subtitle":"永続メモリを表示・編集します。","login":"ログイン","api_key":"APIキー","intro":"キーはこのタブだけに保持されます。","active":"有効","trash":"ごみ箱","new":"新しいメモリ","search":"メモリを検索","key":"キー","value":"値","category":"カテゴリ","importance":"重要度","save":"保存","cancel":"キャンセル","edit":"編集","delete":"ごみ箱へ","restore":"復元","empty":"メモリがありません。","loading":"読み込み中…","saved":"保存しました。","deleted":"ごみ箱へ移動しました。","restored":"復元しました。","confirm_delete":"このメモリをごみ箱へ移動しますか？","invalid_key":"APIキーがないか無効です。","error":"エラー: ","logout":"ログアウト"},
    "ko": {"title":"메모리 관리","subtitle":"영구 메모리를 보고 편집합니다.","login":"로그인","api_key":"API 키","intro":"키는 이 탭에만 보관됩니다.","active":"활성","trash":"휴지통","new":"새 메모리","search":"메모리 검색","key":"키","value":"값","category":"범주","importance":"중요도","save":"저장","cancel":"취소","edit":"편집","delete":"휴지통으로","restore":"복원","empty":"메모리가 없습니다.","loading":"불러오는 중…","saved":"저장했습니다.","deleted":"휴지통으로 이동했습니다.","restored":"복원했습니다.","confirm_delete":"이 메모리를 휴지통으로 이동할까요?","invalid_key":"API 키가 없거나 올바르지 않습니다.","error":"오류: ","logout":"로그아웃"},
    "zh": {"title":"记忆管理","subtitle":"查看和编辑持久记忆。","login":"登录","api_key":"API 密钥","intro":"密钥仅保留在此标签页。","active":"有效","trash":"回收站","new":"新记忆","search":"搜索记忆","key":"键","value":"值","category":"类别","importance":"重要性","save":"保存","cancel":"取消","edit":"编辑","delete":"移到回收站","restore":"恢复","empty":"没有记忆。","loading":"加载中…","saved":"已保存。","deleted":"已移到回收站。","restored":"已恢复。","confirm_delete":"将此记忆移到可恢复回收站？","invalid_key":"API 密钥缺失或无效。","error":"错误：","logout":"退出"},
}

HTML = """<!doctype html>
<html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · House Brain</title><style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#151d33;--line:#2b385a;--text:#eef2ff;--muted:#a8b3cf;--accent:#75a7ff;--danger:#ff7f8f}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#080d19,#111a31);color:var(--text);font:15px system-ui,sans-serif}
main{max-width:1050px;margin:auto;padding:28px 18px 60px}header,.toolbar,.actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header{justify-content:space-between;margin-bottom:20px}h1{margin:0;font-size:28px}p{color:var(--muted)}
.panel,.card{background:rgba(21,29,51,.94);border:1px solid var(--line);border-radius:14px;padding:16px}.panel{margin-bottom:16px}
input,textarea,button{font:inherit;color:var(--text);background:#0d1428;border:1px solid var(--line);border-radius:9px;padding:10px}
textarea{width:100%;min-height:90px;resize:vertical}button{cursor:pointer}button.primary{background:#244f99;border-color:#477bd2}button.danger{color:var(--danger)}
.toolbar input[type=search]{flex:1;min-width:200px}.list{display:grid;gap:12px}.card h3{margin:0 0 8px;word-break:break-word}.meta{color:var(--muted);font-size:13px}.value{white-space:pre-wrap;margin:12px 0}
.form-grid{display:grid;grid-template-columns:1fr 1fr 130px;gap:10px}.form-grid .wide{grid-column:1/-1}.status{min-height:22px;color:var(--muted)}.error{color:var(--danger)}
.tabs button.active{background:#244f99}.hidden{display:none}@media(max-width:650px){.form-grid{grid-template-columns:1fr}}
</style></head><body><main>
<header><div><h1>__TITLE__</h1><p>__SUBTITLE__</p></div><button id="logout" class="hidden">__LOGOUT__</button></header>
<section id="auth" class="panel"><form id="authForm"><p>__INTRO__</p><input id="apiKey" type="password" autocomplete="current-password" placeholder="__API_KEY__" required> <button class="primary">__LOGIN__</button><div id="authError" class="status error"></div></form></section>
<section id="app" class="hidden">
<div class="panel"><div class="toolbar"><input id="search" type="search" placeholder="__SEARCH__"><div class="tabs"><button id="activeTab" class="active">__ACTIVE__</button><button id="trashTab">__TRASH__</button></div><button id="newButton" class="primary">__NEW__</button></div><div id="status" class="status"></div></div>
<form id="editor" class="panel hidden"><div class="form-grid"><input id="key" placeholder="__KEY__" maxlength="120" required><input id="category" placeholder="__CATEGORY__" maxlength="50" value="fact" required><input id="importance" type="number" min="1" max="10" value="5" required><textarea id="value" class="wide" placeholder="__VALUE__" maxlength="2000" required></textarea></div><div class="actions"><button class="primary">__SAVE__</button><button id="cancel" type="button">__CANCEL__</button></div></form>
<div id="list" class="list"></div>
</section></main><script>
(()=>{"use strict";const i18n=__I18N__,KEY="house_brain_api_key";let deleted=false,items=[];
const $=id=>document.getElementById(id),apiKey=()=>sessionStorage.getItem(KEY)||"";
async function api(path,options={}){const headers=new Headers(options.headers||{});headers.set("X-API-Key",apiKey());if(options.body)headers.set("Content-Type","application/json");return fetch(path,{...options,headers});}
function message(text,error=false){$("status").textContent=text;$("status").className="status"+(error?" error":"");}
function showEditor(item=null){$("editor").classList.remove("hidden");$("key").value=item?.key||"";$("key").readOnly=Boolean(item);$("value").value=item?.value||"";$("category").value=item?.category||"fact";$("importance").value=item?.importance||5;$("value").focus();}
function hideEditor(){$("editor").classList.add("hidden");$("editor").reset();$("key").readOnly=false;$("category").value="fact";$("importance").value=5;}
function render(){const q=$("search").value.trim().toLocaleLowerCase();const shown=items.filter(x=>(x.key+" "+x.value+" "+x.category).toLocaleLowerCase().includes(q));$("list").replaceChildren();if(!shown.length){const e=document.createElement("div");e.className="panel";e.textContent=i18n.empty;$("list").append(e);return;}for(const item of shown){const card=document.createElement("article");card.className="card";const title=document.createElement("h3");title.textContent=item.key;const meta=document.createElement("div");meta.className="meta";meta.textContent=item.category+" · "+i18n.importance+": "+item.importance;const value=document.createElement("div");value.className="value";value.textContent=item.value;const actions=document.createElement("div");actions.className="actions";if(deleted){const restore=document.createElement("button");restore.textContent=i18n.restore;restore.onclick=()=>restoreItem(item.key);actions.append(restore);}else{const edit=document.createElement("button");edit.textContent=i18n.edit;edit.onclick=()=>showEditor(item);const remove=document.createElement("button");remove.className="danger";remove.textContent=i18n.delete;remove.onclick=()=>removeItem(item.key);actions.append(edit,remove);}card.append(title,meta,value,actions);$("list").append(card);}}
async function load(){message(i18n.loading);const response=await api("/memory?limit=5000&deleted="+deleted);if(response.status===401)throw new Error(i18n.invalid_key);const body=await response.json();if(!response.ok)throw new Error(body.detail||response.statusText);items=body;render();message("");$("auth").classList.add("hidden");$("app").classList.remove("hidden");$("logout").classList.remove("hidden");}
async function save(event){event.preventDefault();const body={key:$("key").value.trim(),value:$("value").value.trim(),category:$("category").value.trim(),importance:Number($("importance").value)};const response=await api("/memory",{method:"POST",body:JSON.stringify(body)});const payload=await response.json();if(!response.ok)throw new Error(payload.detail||response.statusText);hideEditor();await load();message(i18n.saved);}
async function removeItem(key){if(!confirm(i18n.confirm_delete))return;const response=await api("/memory/"+encodeURIComponent(key),{method:"DELETE"});const payload=await response.json();if(!response.ok)throw new Error(payload.detail||response.statusText);await load();message(i18n.deleted);}
async function restoreItem(key){const response=await api("/memory/"+encodeURIComponent(key)+"/restore",{method:"POST"});const payload=await response.json();if(!response.ok)throw new Error(payload.detail||response.statusText);await load();message(i18n.restored);}
function guard(fn){return async(...args)=>{try{await fn(...args);}catch(error){message(i18n.error+error.message,true);}}}
$("authForm").onsubmit=guard(async event=>{event.preventDefault();sessionStorage.setItem(KEY,$("apiKey").value);await load();});
$("editor").onsubmit=guard(save);$("cancel").onclick=hideEditor;$("newButton").onclick=()=>showEditor();$("search").oninput=render;
$("activeTab").onclick=guard(async()=>{deleted=false;$("activeTab").classList.add("active");$("trashTab").classList.remove("active");hideEditor();await load();});
$("trashTab").onclick=guard(async()=>{deleted=true;$("trashTab").classList.add("active");$("activeTab").classList.remove("active");hideEditor();await load();});
$("logout").onclick=()=>{sessionStorage.removeItem(KEY);location.reload();};
if(apiKey())load().catch(error=>{sessionStorage.removeItem(KEY);$("authError").textContent=error.message;});
})();</script></body></html>"""


def memory_page(language: str) -> HTMLResponse:
    """Return the authenticated persistent-memory manager shell."""
    family = language_family(language)
    messages = MESSAGES.get(family, MESSAGES["en"])
    replacements = {
        "__LANG__": family,
        "__I18N__": json.dumps(messages, ensure_ascii=True).replace("<", "\\u003c"),
        **{f"__{key.upper()}__": value for key, value in messages.items()},
    }
    html = HTML
    html = html.replace("</style>", f"{SHARED_THEME_CSS}</style>", 1)
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
