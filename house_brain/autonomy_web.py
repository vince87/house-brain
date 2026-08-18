# ruff: noqa: E501

import json

from fastapi.responses import HTMLResponse

from house_brain.languages import language_family, localized_autonomy_ui_messages

AUTONOMY_HTML = r"""<!doctype html>
<html lang="__LANG__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>House Brain · __TITLE__</title>
  <style>
    :root { --bg:#0b1020; --panel:#151d33; --line:#2b385a; --text:#eef2ff;
      --muted:#a8b3cf; --accent:#75a7ff; --danger:#ff8a80; }
    * { box-sizing:border-box; }
    body { margin:0; background:linear-gradient(145deg,#080d19,#111a31); color:var(--text);
      font:15px/1.45 system-ui,sans-serif; }
    button,input,select,textarea { font:inherit; }
    .shell { width:min(1200px,100%); margin:auto; padding:18px; }
    header,.panel { border:1px solid var(--line); border-radius:16px;
      background:var(--panel); padding:16px; margin-bottom:14px; }
    header { display:flex; justify-content:space-between; gap:14px; align-items:center; }
    h1 { margin:0; font-size:1.2rem; } p { margin:.3rem 0; color:var(--muted); }
    .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
    input,select,textarea { color:var(--text); background:#0d1428;
      border:1px solid var(--line); border-radius:10px; padding:10px; }
    input[type=search] { flex:1; min-width:220px; }
    textarea { width:100%; min-height:90px; resize:vertical; }
    button { color:#080d19; background:var(--accent); border:0; border-radius:10px;
      padding:10px 14px; font-weight:700; cursor:pointer; }
    button.secondary { color:var(--text); background:#0d1428; border:1px solid var(--line); }
    button:disabled { opacity:.5; cursor:wait; }
    .status { min-height:1.4em; color:var(--muted); margin-top:10px; }
    .status.error { color:var(--danger); }
    .list { display:grid; gap:8px; margin-top:12px; }
    .entity { display:grid; grid-template-columns:minmax(230px,1fr) auto auto auto minmax(190px,.7fr);
      gap:10px; align-items:center; border:1px solid var(--line); border-radius:12px;
      padding:10px; }
    .entity-id { font-family:ui-monospace,monospace; overflow-wrap:anywhere; }
    .friendly { color:var(--muted); font-size:.86rem; }
    label.toggle { white-space:nowrap; }
    .code-input[hidden] { display:none; }
    [hidden] { display:none !important; }
    @media (max-width:780px) { .entity { grid-template-columns:1fr 1fr; }
      .identity { grid-column:1/-1; } .code-input { grid-column:1/-1; width:100%; } }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div><h1>__TITLE__</h1><p>__SUBTITLE__</p></div>
      <button class="secondary" id="logout" type="button" hidden>__LOGOUT__</button>
    </header>

    <section class="panel" id="authPanel">
      <h2>__LOGIN__</h2><p>__INTRO__</p>
      <form class="row" id="authForm">
        <input id="apiKey" type="password" placeholder="__API_KEY__" required>
        <button type="submit">__LOGIN__</button>
      </form>
      <div class="status error" id="authError"></div>
    </section>

    <main id="editor" hidden>
      <section class="panel">
        <div class="row">
          <input id="search" type="search" placeholder="__SEARCH__">
          <select id="domain"><option value="">__ALL_DOMAINS__</option></select>
        </div>
        <div class="list" id="entities"></div>
        <div class="status" id="empty" hidden>__EMPTY__</div>
      </section>
      <section class="panel">
        <label for="patterns">__PATTERNS__</label>
        <textarea id="patterns" spellcheck="false"></textarea>
        <div class="row">
          <button id="save" type="button">__SAVE__</button>
          <div class="status" id="status"></div>
        </div>
      </section>
    </main>
  </div>
  <script>
    (() => {
      "use strict";
      const i18n = __I18N__;
      const KEY_NAME = "house_brain_api_key";
      const authPanel = document.getElementById("authPanel");
      const editor = document.getElementById("editor");
      const entitiesNode = document.getElementById("entities");
      const patternsNode = document.getElementById("patterns");
      const statusNode = document.getElementById("status");
      const emptyNode = document.getElementById("empty");
      const searchNode = document.getElementById("search");
      const domainNode = document.getElementById("domain");
      const logout = document.getElementById("logout");
      let entities = [];

      function apiKey() { return sessionStorage.getItem(KEY_NAME) || ""; }
      async function api(path, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set("X-API-Key", apiKey());
        if (options.body) headers.set("Content-Type", "application/json");
        const response = await fetch(path, {...options, headers});
        if (response.status === 401) throw new Error(i18n.invalid_key);
        return response;
      }
      function setStatus(message, error = false) {
        statusNode.textContent = message;
        statusNode.classList.toggle("error", error);
      }
      function toggleCode(row) {
        row.codeInput.hidden = !row.codeRequired.checked;
        if (!row.codeRequired.checked) row.codeInput.value = "";
      }
      function render() {
        const query = searchNode.value.trim().toLocaleLowerCase();
        const domain = domainNode.value;
        let visible = 0;
        for (const row of entities) {
          const matches = (!domain || row.domain === domain)
            && (!query || row.searchText.includes(query));
          row.node.hidden = !matches;
          if (matches) visible += 1;
        }
        emptyNode.hidden = visible !== 0;
      }
      function entityRow(item, configured, excluded) {
        const node = document.createElement("div"); node.className = "entity";
        const identity = document.createElement("div"); identity.className = "identity";
        const entityId = document.createElement("div"); entityId.className = "entity-id";
        entityId.textContent = item.entity_id;
        const friendly = document.createElement("div"); friendly.className = "friendly";
        friendly.textContent = item.friendly_name + " · " + item.state;
        identity.append(entityId, friendly);
        const includeLabel = document.createElement("label"); includeLabel.className = "toggle";
        const include = document.createElement("input"); include.type = "checkbox";
        include.checked = Boolean(configured); includeLabel.append(include, " " + i18n.included);
        const excludeLabel = document.createElement("label"); excludeLabel.className = "toggle";
        const exclude = document.createElement("input"); exclude.type = "checkbox";
        exclude.checked = excluded; excludeLabel.append(exclude, " " + i18n.excluded);
        const codeLabel = document.createElement("label"); codeLabel.className = "toggle";
        const codeRequired = document.createElement("input"); codeRequired.type = "checkbox";
        codeRequired.checked = Boolean(configured && configured.code_required);
        codeLabel.append(codeRequired, " " + i18n.code);
        const codeInput = document.createElement("input"); codeInput.type = "password";
        codeInput.className = "code-input"; codeInput.placeholder = i18n.new_code;
        const row = {node, include, exclude, codeRequired, codeInput,
          entityId:item.entity_id, domain:item.domain,
          searchText:(item.entity_id + " " + item.friendly_name).toLocaleLowerCase()};
        include.addEventListener("change", () => {
          if (include.checked) exclude.checked = false;
          codeRequired.disabled = !include.checked;
          if (!include.checked) codeRequired.checked = false;
          toggleCode(row);
        });
        exclude.addEventListener("change", () => {
          if (exclude.checked) { include.checked = false; codeRequired.checked = false; }
          codeRequired.disabled = !include.checked; toggleCode(row);
        });
        codeRequired.addEventListener("change", () => toggleCode(row));
        codeRequired.disabled = !include.checked; toggleCode(row);
        node.append(identity, includeLabel, excludeLabel, codeLabel, codeInput);
        entitiesNode.appendChild(node); return row;
      }
      async function load() {
        setStatus(i18n.loading);
        const response = await api("/admin/autonomy");
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || i18n.error);
        const included = new Map(payload.configuration.include.map(item => [item.entity_id, item]));
        const knownIds = new Set(payload.entities.map(item => item.entity_id));
        const excluded = new Set(payload.configuration.exclude.filter(item => knownIds.has(item)));
        patternsNode.value = payload.configuration.exclude.filter(item => !knownIds.has(item)).join("\n");
        entitiesNode.replaceChildren();
        entities = payload.entities.map(item => entityRow(item, included.get(item.entity_id), excluded.has(item.entity_id)));
        const domains = [...new Set(payload.entities.map(item => item.domain))].sort();
        for (const domain of domains) { const option = document.createElement("option");
          option.value = domain; option.textContent = domain; domainNode.appendChild(option); }
        authPanel.hidden = true; editor.hidden = false; logout.hidden = false; setStatus(""); render();
      }
      async function save() {
        if (!confirm(i18n.confirm)) return;
        const include = entities.filter(row => row.include.checked).map(row => ({
          entity_id: row.entityId, code_required: row.codeRequired.checked,
          code: row.codeInput.value || null,
        }));
        const excludedEntities = entities.filter(row => row.exclude.checked).map(row => row.entityId);
        const extra = patternsNode.value.split(/\r?\n/).map(item => item.trim()).filter(Boolean);
        document.getElementById("save").disabled = true; setStatus("");
        try {
          const response = await api("/admin/autonomy", {method:"PUT",
            body:JSON.stringify({include, exclude:[...excludedEntities, ...extra]})});
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.detail || i18n.error);
          for (const row of entities) row.codeInput.value = "";
          setStatus(i18n.saved);
        } catch (error) { setStatus(i18n.error + error.message, true); }
        finally { document.getElementById("save").disabled = false; }
      }
      document.getElementById("authForm").addEventListener("submit", async event => {
        event.preventDefault(); sessionStorage.setItem(KEY_NAME, document.getElementById("apiKey").value);
        try { await load(); } catch (error) { document.getElementById("authError").textContent = error.message; }
      });
      searchNode.addEventListener("input", render); domainNode.addEventListener("change", render);
      document.getElementById("save").addEventListener("click", save);
      logout.addEventListener("click", () => { sessionStorage.removeItem(KEY_NAME); location.reload(); });
      if (apiKey()) load().catch(error => { sessionStorage.removeItem(KEY_NAME);
        document.getElementById("authError").textContent = error.message; });
    })();
  </script>
</body>
</html>
"""


def autonomy_page(language: str) -> HTMLResponse:
    """Return the authenticated policy configurator shell."""
    messages = localized_autonomy_ui_messages(language)
    replacements = {
        "__LANG__": language_family(language),
        "__I18N__": json.dumps(messages, ensure_ascii=True).replace("<", "\\u003c"),
        **{f"__{key.upper()}__": value for key, value in messages.items()},
    }
    html = AUTONOMY_HTML
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
