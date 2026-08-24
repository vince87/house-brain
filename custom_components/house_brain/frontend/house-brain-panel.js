const SECTIONS = ["chat", "memories", "audit", "plans", "autonomy", "context", "logs", "installation", "diagnostics"];

const LABELS = {
  en: {
    chat: "Chat", memories: "Memories", audit: "Audit", plans: "Action plans", autonomy: "Autonomy", context: "Context",
    logs: "Logs", installation: "Installation", diagnostics: "Diagnostics", refresh: "Refresh", loading: "Loading…",
    error: "Error: ", empty: "No items to display.", send: "Send",
    message: "Write a message", newChat: "New chat", clearChat: "Clear history",
    confirmClear: "Permanently clear this conversation?", tools: "Tools: ",
    mode: "Mode", active: "Active", trash: "Trash", add: "Add",
    edit: "Edit", remove: "Move to trash", restore: "Restore", save: "Save",
    cancel: "Cancel", key: "Key", value: "Value", category: "Category",
    importance: "Importance", expires: "Expires", never: "Never",
    search: "Search", export: "Export", import: "Import", source: "Source",
    instruction: "Instruction", response: "Final response", trace: "Full tool trace",
    allModes: "All modes", allStatuses: "All statuses", total: "Total",
    completed: "Completed", failed: "Failed", visible: "Visible only",
    controllable: "Controllable", notVisible: "Not visible", entityName: "Authoritative name",
    codeRequired: "Requires code", newCode: "New code (leave empty to keep it)",
    domain: "All domains", savePolicy: "Save policy",
    confirmPolicy: "Save the new global entity policy?", saved: "Changes saved.",
    level: "All levels", automatic: "Auto refresh", applicationLogs: "Application logs",
    download: "Download JSON", healthy: "Operational", degraded: "Degraded",
    homeAssistant: "Home Assistant", llm: "LLM provider", persistence: "Persistence",
    nativeNotice: "This interface runs inside Home Assistant. Requests are proxied securely by the integration.",
    deleteMemory: "Move this memory to the trash?", result: "Result",
    entities: "Referenced entities", verified: "Verified", unverified: "Not verified",
    providerMetrics: "Provider metrics", installationState: "Installation state", schemaVersion: "Schema version", preRestoreBackups: "Recovery snapshots", lifecycleSafety: "Backup and restore operations remain available in the authenticated House Brain installation page.", requested: "Requested", validation: "Validation",
    homeAssistantCall: "Home Assistant call", outcome: "Outcome", notCalled: "Not called",
    proposePlan: "Simulate and propose", planInstruction: "What should House Brain plan?",
    approvePlan: "Approve and execute", rejectPlan: "Reject", initialState: "Initial state",
    policyCode: "Optional policy code", haCode: "Optional Home Assistant code",
    contextPolicy: "Views only narrow the global Autonomy policy.", contextAdd: "New view", contextDefault: "Default view", contextNone: "None", contextEnabled: "Enabled", contextMemories: "Include linked memories", contextAreas: "Areas (comma-separated)", contextDomains: "Domains (comma-separated)", contextEntities: "Entities (comma-separated)", contextLimit: "Entity limit", contextPreview: "Preview", contextRemove: "Remove view", contextSelected: "entities selected", contextOmitted: "omitted by limit",
  },
  it: {
    chat: "Chat", memories: "Memorie", audit: "Audit", plans: "Piani", autonomy: "Autonomia", context: "Contesto",
    logs: "Log", installation: "Installazione", diagnostics: "Diagnostica", refresh: "Aggiorna", loading: "Caricamento…",
    error: "Errore: ", empty: "Nessun elemento da mostrare.", send: "Invia",
    message: "Scrivi un messaggio", newChat: "Nuova chat", clearChat: "Cancella cronologia",
    confirmClear: "Eliminare definitivamente questa conversazione?", tools: "Strumenti: ",
    mode: "Modalità", active: "Attive", trash: "Cestino", add: "Aggiungi",
    edit: "Modifica", remove: "Sposta nel cestino", restore: "Ripristina", save: "Salva",
    cancel: "Annulla", key: "Chiave", value: "Valore", category: "Categoria",
    importance: "Importanza", expires: "Scadenza", never: "Mai",
    search: "Cerca", export: "Esporta", import: "Importa", source: "Origine",
    instruction: "Istruzione", response: "Risposta finale", trace: "Tool trace completa",
    allModes: "Tutte le modalità", allStatuses: "Tutti gli stati", total: "Totale",
    completed: "Completati", failed: "Falliti", visible: "Solo visibile",
    controllable: "Controllabile", notVisible: "Non visibile", entityName: "Nome autorevole",
    codeRequired: "Richiede codice", newCode: "Nuovo codice (vuoto per conservarlo)",
    domain: "Tutti i domini", savePolicy: "Salva policy",
    confirmPolicy: "Salvare la nuova policy globale delle entità?", saved: "Modifiche salvate.",
    level: "Tutti i livelli", automatic: "Aggiornamento automatico", applicationLogs: "Log applicativi",
    download: "Scarica JSON", healthy: "Operativo", degraded: "Degradato",
    homeAssistant: "Home Assistant", llm: "Provider LLM", persistence: "Persistenza",
    nativeNotice: "Questa interfaccia gira dentro Home Assistant. Le richieste sono inoltrate in sicurezza dall'integrazione.",
    deleteMemory: "Spostare questa memoria nel cestino?", result: "Risultato",
    entities: "Entità citate", verified: "Verificata", unverified: "Non verificata",
    providerMetrics: "Metriche provider", installationState: "Stato installazione", schemaVersion: "Versione schema", preRestoreBackups: "Snapshot di recupero", lifecycleSafety: "Le operazioni di backup e ripristino restano disponibili nella pagina autenticata Installazione di House Brain.", requested: "Richiesta", validation: "Validazione",
    homeAssistantCall: "Chiamata Home Assistant", outcome: "Esito", notCalled: "Non effettuata",
    proposePlan: "Simula e proponi", planInstruction: "Cosa deve pianificare House Brain?",
    approvePlan: "Approva ed esegui", rejectPlan: "Rifiuta", initialState: "Stato iniziale",
    policyCode: "Codice policy opzionale", haCode: "Codice Home Assistant opzionale",
    contextPolicy: "Le viste possono soltanto restringere la policy globale di Autonomia.", contextAdd: "Nuova vista", contextDefault: "Vista predefinita", contextNone: "Nessuna", contextEnabled: "Abilitata", contextMemories: "Includi memorie collegate", contextAreas: "Aree (separate da virgole)", contextDomains: "Domini (separati da virgole)", contextEntities: "Entità (separate da virgole)", contextLimit: "Limite entità", contextPreview: "Anteprima", contextRemove: "Rimuovi vista", contextSelected: "entità selezionate", contextOmitted: "omesse dal limite",
  },
};

const html = (strings, ...values) => strings.reduce(
  (result, part, index) => result + part + (values[index] ?? ""), ""
);

class HouseBrainPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._section = "chat";
    this._initialized = false;
    this._loadToken = 0;
    this._logTimer = null;
    this._memories = [];
    this._events = [];
    this._autonomyState = new Map();
  }

  set hass(value) {
    this._hass = value;
    this._ensureShell();
  }

  set panel(value) {
    const previous = this._panel?.config?.entry_id;
    this._panel = value;
    if (previous && previous !== value?.config?.entry_id) {
      this._initialized = false;
      this.shadowRoot.replaceChildren();
    }
    this._ensureShell();
  }

  set narrow(value) {
    this.toggleAttribute("narrow", Boolean(value));
  }

  connectedCallback() {
    this._ensureShell();
  }

  disconnectedCallback() {
    this._stopLogTimer();
  }

  _labels() {
    const language = this._hass?.locale?.language || this._hass?.language || "en";
    return LABELS[language.split("-")[0]] || LABELS.en;
  }

  _ensureShell() {
    if (this._initialized || !this.isConnected || !this._hass || !this._panel) {
      return;
    }
    this._initialized = true;
    const t = this._labels();
    this.shadowRoot.innerHTML = html`
      <style>
        :host {
          display:block; height:100%; min-height:0; color:var(--primary-text-color);
          background:var(--primary-background-color); font-family:Roboto,system-ui,sans-serif;
          --hb-blue:var(--primary-color,#03a9f4); --hb-card:var(--ha-card-background,var(--card-background-color,#fff));
          --hb-border:var(--divider-color,#e0e0e0); --hb-muted:var(--secondary-text-color,#727272);
          --hb-error:var(--error-color,#db4437); --hb-ok:var(--success-color,#43a047);
        }
        *{box-sizing:border-box} button,input,select,textarea{font:inherit}
        .app{height:100%;min-height:0;display:grid;grid-template-rows:auto 1fr}
        .toolbar{min-height:64px;display:flex;align-items:center;gap:14px;padding:0 18px;
          background:var(--app-header-background-color,var(--hb-card));color:var(--app-header-text-color,var(--primary-text-color));
          border-bottom:1px solid var(--hb-border);box-shadow:0 1px 3px rgba(0,0,0,.14);z-index:2}
        .brand{display:flex;align-items:center;gap:10px;white-space:nowrap;font-size:1.05rem;font-weight:500}
        .mark{width:38px;height:38px;display:grid;place-items:center;border-radius:10px;background:var(--hb-blue);
          color:#fff;font-size:.8rem;font-weight:800}
        nav{min-width:0;flex:1;align-self:stretch;display:flex;overflow-x:auto;scrollbar-width:none}
        nav::-webkit-scrollbar{display:none}
        .tab{min-width:max-content;padding:0 14px;border:0;border-bottom:3px solid transparent;
          color:var(--hb-muted);background:transparent;cursor:pointer}
        .tab:hover{color:var(--primary-text-color);background:color-mix(in srgb,var(--hb-blue) 10%,transparent)}
        .tab.active{color:var(--hb-blue);border-bottom-color:var(--hb-blue)}
        .mode{padding:5px 10px;border:1px solid color-mix(in srgb,var(--hb-blue) 45%,var(--hb-border));
          border-radius:999px;color:var(--hb-blue);font-size:.78rem;white-space:nowrap}
        .viewport{min-height:0;overflow:auto;padding:20px;background:var(--primary-background-color)}
        .page{width:min(1180px,100%);margin:0 auto;display:grid;gap:16px}
        .page-title{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
        h1,h2,h3,p{margin-top:0} h1{margin-bottom:4px;font-size:1.8rem;font-weight:500}
        h2{font-size:1.15rem;font-weight:500} h3{font-size:1rem}
        .muted,.meta{color:var(--hb-muted)} .notice{font-size:.88rem}
        .card{padding:18px;border:1px solid var(--hb-border);border-radius:12px;background:var(--hb-card);
          box-shadow:var(--ha-card-box-shadow,0 2px 5px rgba(0,0,0,.12))}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
        .row,.actions,.filters{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
        .actions{margin-top:14px}.filters{padding:14px}
        input,select,textarea{min-height:42px;padding:9px 11px;border:1px solid var(--hb-border);border-radius:8px;
          color:var(--primary-text-color);background:var(--input-fill-color,var(--secondary-background-color))}
        input[type="search"],.grow{flex:1;min-width:180px} textarea{width:100%;min-height:100px;resize:vertical}
        button,.button{min-height:40px;padding:8px 14px;border:1px solid var(--hb-border);border-radius:8px;
          color:var(--primary-text-color);background:var(--secondary-background-color);cursor:pointer}
        button:hover{border-color:var(--hb-blue)} button.primary{border-color:var(--hb-blue);background:var(--hb-blue);color:#fff}
        button.danger{color:var(--hb-error)} button:disabled{opacity:.5;cursor:wait}
        .status{min-height:22px;color:var(--hb-muted)}.status.error{color:var(--hb-error)}
        .badge{display:inline-flex;padding:4px 9px;margin:0 5px 5px 0;border:1px solid var(--hb-border);
          border-radius:999px;font-size:.78rem}.badge.completed,.badge.executed,.badge.simulated{color:var(--hb-ok)}
        .badge.failed,.badge.rejected{color:var(--hb-error)}
        .chat{height:min(680px,calc(100vh - 190px));min-height:430px;display:grid;grid-template-rows:1fr auto;padding:0;overflow:hidden}
        .messages{min-height:0;overflow:auto;padding:18px;display:flex;flex-direction:column;gap:12px}
        .message{max-width:min(760px,88%);padding:12px 14px;border-radius:12px;background:var(--secondary-background-color);
          white-space:pre-wrap;overflow-wrap:anywhere}.message.user{align-self:flex-end;background:color-mix(in srgb,var(--hb-blue) 18%,var(--hb-card))}
        .message.assistant{align-self:flex-start}.composer{padding:14px;border-top:1px solid var(--hb-border);display:flex;gap:10px}
        .composer textarea{min-height:46px;max-height:150px}.trace{margin-top:10px}
        details{margin-top:10px;border:1px solid var(--hb-border);border-radius:8px;padding:9px}
        summary{color:var(--hb-blue);cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;color:var(--hb-muted)}
        .memory-value,.event-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55}
        .memory-card{display:flex;flex-direction:column;min-height:210px}.memory-value{flex:1}
        .entity-links{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.entity-link{padding:5px 9px;border:1px solid var(--hb-border);border-radius:999px;color:var(--hb-muted);text-decoration:none;font-size:.8rem}.entity-link.verified{border-color:color-mix(in srgb,var(--hb-ok) 55%,var(--hb-border));color:var(--hb-ok)}
        .audit-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.audit-stage{padding:10px;border-left:3px solid var(--hb-blue);background:var(--secondary-background-color);border-radius:7px;overflow-wrap:anywhere}.audit-stage strong{display:block;font-size:.78rem;color:var(--hb-muted);margin-bottom:5px}
        .editor-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.editor-grid .wide{grid-column:1/-1}
        .insights{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
        .insight strong{display:block;font-size:1.6rem}.insight span{color:var(--hb-muted)}
        .entity{display:grid;grid-template-columns:minmax(230px,1.1fr) minmax(180px,.8fr) 170px auto;gap:10px;align-items:center}
        .entity-id{font-family:monospace;overflow-wrap:anywhere}.entity-state{font-size:.82rem;color:var(--hb-muted)}
        .code-box{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.code-box input[type="password"]{width:220px}
        .log-entry{display:grid;grid-template-columns:170px 90px minmax(170px,.5fr) 1fr;gap:10px;align-items:start}
        .log-entry .log-message{overflow-wrap:anywhere}.ERROR,.CRITICAL{color:var(--hb-error)}.WARNING{color:var(--warning-color,#f9a825)}
        .summary-line{display:flex;align-items:center;gap:10px}.dot{width:14px;height:14px;border-radius:50%;background:var(--hb-ok)}
        .degraded .dot{background:var(--hb-error)}
        @media(max-width:760px){
          .toolbar{min-height:58px;padding:0 8px;gap:7px}.brand span:last-child,.mode{display:none}.mark{width:36px;height:36px}
          .tab{padding:0 10px;font-size:.78rem}.viewport{padding:12px}.editor-grid{grid-template-columns:1fr}
          .entity{grid-template-columns:1fr}.log-entry{grid-template-columns:1fr}.chat{height:calc(100vh - 145px)}
          .insights,.audit-flow{grid-template-columns:1fr}.composer{align-items:flex-end}
        }
      </style>
      <div class="app">
        <header class="toolbar">
          <div class="brand"><span class="mark">HB</span><span>House Brain</span></div>
          <nav aria-label="House Brain">
            ${SECTIONS.map(section => `<button class="tab" data-section="${section}">${t[section]}</button>`).join("")}
          </nav>
          <span class="mode"></span>
        </header>
        <main class="viewport"><div class="page"></div></main>
      </div>`;
    this._content = this.shadowRoot.querySelector(".page");
    this.shadowRoot.querySelector(".mode").textContent =
      `${t.mode}: ${this._panel.config.mode || "observe"}`;
    this.shadowRoot.querySelectorAll(".tab").forEach(button => {
      button.addEventListener("click", () => this._navigate(button.dataset.section));
    });
    this._navigate(this._section);
  }

  async _call(operation, payload = {}) {
    return this._hass.callWS({
      type: "house_brain/panel",
      entry_id: this._panel.config.entry_id,
      operation,
      payload,
    });
  }

  _navigate(section) {
    if (!SECTIONS.includes(section)) return;
    this._section = section;
    this._stopLogTimer();
    this.shadowRoot.querySelectorAll(".tab").forEach(button => {
      button.classList.toggle("active", button.dataset.section === section);
    });
    this._loadSection();
  }

  async _loadSection() {
    const token = ++this._loadToken;
    const t = this._labels();
    this._content.innerHTML = `<div class="card status">${t.loading}</div>`;
    try {
      if (this._section === "chat") await this._chat(token);
      if (this._section === "memories") await this._memoryPage(token);
      if (this._section === "audit") await this._auditPage(token);
      if (this._section === "plans") await this._plansPage(token);
      if (this._section === "autonomy") await this._autonomyPage(token);
      if (this._section === "context") await this._contextPage(token);
      if (this._section === "logs") await this._logsPage(token);
      if (this._section === "installation") await this._installationPage(token);
      if (this._section === "diagnostics") await this._diagnosticsPage(token);
    } catch (error) {
      if (token === this._loadToken) this._showError(error);
    }
  }

  _showError(error) {
    const t = this._labels();
    this._content.innerHTML = "";
    const card = document.createElement("div");
    card.className = "card status error";
    card.textContent = t.error + (error?.message || String(error));
    const retry = document.createElement("button");
    retry.textContent = t.refresh;
    retry.addEventListener("click", () => this._loadSection());
    card.append(document.createElement("br"), retry);
    this._content.append(card);
  }

  _title(name, actions = []) {
    const t = this._labels();
    const header = document.createElement("div");
    header.className = "page-title";
    const text = document.createElement("div");
    const heading = document.createElement("h1");
    heading.textContent = t[name];
    const notice = document.createElement("p");
    notice.className = "muted notice";
    notice.textContent = t.nativeNotice;
    text.append(heading, notice);
    const buttons = document.createElement("div");
    buttons.className = "row";
    actions.forEach(button => buttons.append(button));
    header.append(text, buttons);
    return header;
  }

  _button(label, handler, className = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.className = className;
    button.addEventListener("click", handler);
    return button;
  }

  _status(parent) {
    const node = document.createElement("div");
    node.className = "status";
    parent.append(node);
    return (message, error = false) => {
      node.textContent = message;
      node.classList.toggle("error", error);
    };
  }

  _download(name, value) {
    const blob = new Blob([JSON.stringify(value, null, 2)], {type: "application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = name;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  _sessionId() {
    const key = `house_brain_panel_session_${this._panel.config.entry_id}`;
    let value = sessionStorage.getItem(key);
    if (!value) {
      const suffix = crypto.randomUUID ? crypto.randomUUID() :
        Date.now().toString(36) + Math.random().toString(36).slice(2);
      value = (`ha-panel-${suffix}`).slice(0, 64);
      sessionStorage.setItem(key, value);
    }
    return value;
  }

  _newSession() {
    const key = `house_brain_panel_session_${this._panel.config.entry_id}`;
    sessionStorage.removeItem(key);
    return this._sessionId();
  }

  _appendMessage(container, role, content, payload = null) {
    const t = this._labels();
    const item = document.createElement("article");
    item.className = `message ${role}`;
    const text = document.createElement("div");
    text.textContent = content;
    item.append(text);
    if (payload?.tools_used?.length) {
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = t.tools + payload.tools_used.join(", ");
      item.append(meta);
    }
    if (payload?.tool_trace?.length) {
      const details = document.createElement("details");
      details.className = "trace";
      const summary = document.createElement("summary");
      summary.textContent = t.trace;
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(payload.tool_trace, null, 2);
      details.append(summary, pre);
      item.append(details);
    }
    container.append(item);
    container.scrollTop = container.scrollHeight;
    return item;
  }

  async _chat(token) {
    const t = this._labels();
    this._content.innerHTML = "";
    const newButton = this._button(t.newChat, async () => {
      this._newSession();
      await this._chat(++this._loadToken);
    });
    const clearButton = this._button(t.clearChat, async () => {
      if (!confirm(t.confirmClear)) return;
      await this._call("conversation_clear", {session_id: this._sessionId()});
      messages.replaceChildren();
    }, "danger");
    this._content.append(this._title("chat", [newButton, clearButton]));
    const chat = document.createElement("section");
    chat.className = "card chat";
    const messages = document.createElement("div");
    messages.className = "messages";
    const form = document.createElement("form");
    form.className = "composer";
    const input = document.createElement("textarea");
    input.className = "grow";
    input.placeholder = t.message;
    input.rows = 1;
    const send = document.createElement("button");
    send.className = "primary";
    send.textContent = t.send;
    form.append(input, send);
    chat.append(messages, form);
    this._content.append(chat);

    const history = await this._call("conversation_get", {session_id: this._sessionId()});
    if (token !== this._loadToken) return;
    for (const item of history) {
      this._appendMessage(messages, item.role || "assistant", item.content || "", item);
    }

    form.addEventListener("submit", async event => {
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;
      this._appendMessage(messages, "user", message);
      input.value = "";
      input.disabled = true;
      send.disabled = true;
      const pending = this._appendMessage(messages, "assistant", t.loading);
      try {
        const result = await this._call("chat", {
          message,
          session_id: this._sessionId(),
        });
        pending.remove();
        this._appendMessage(messages, "assistant", result.response, result);
      } catch (error) {
        pending.textContent = t.error + (error?.message || String(error));
        pending.classList.add("error");
      } finally {
        input.disabled = false;
        send.disabled = false;
        input.focus();
      }
    });
    input.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });
  }

  async _memoryPage(token, deleted = false) {
    const t = this._labels();
    const items = await this._call("memory_list", {deleted});
    if (token !== this._loadToken) return;
    this._memories = items;
    this._content.innerHTML = "";
    const add = this._button(t.add, () => this._memoryEditor(null, deleted), "primary");
    const exportButton = this._button(t.export, () => {
      this._download("house-brain-memories.json", this._memories.map(item => ({
        key:item.key, value:item.value, category:item.category,
        importance:item.importance, expires_at:item.expires_at,
      })));
    });
    const importButton = this._button(t.import, () => file.click());
    const file = document.createElement("input");
    file.type = "file"; file.accept = "application/json"; file.hidden = true;
    file.addEventListener("change", async () => {
      const selected = file.files?.[0];
      if (!selected) return;
      const values = JSON.parse(await selected.text());
      await this._call("memory_import", {items: values});
      await this._memoryPage(++this._loadToken, false);
    });
    this._content.append(this._title("memories", [add, exportButton, importButton]), file);
    const filters = document.createElement("div");
    filters.className = "card filters";
    const search = document.createElement("input");
    search.type = "search"; search.placeholder = t.search; search.className = "grow";
    const active = this._button(t.active, () => this._memoryPage(++this._loadToken, false), deleted ? "" : "primary");
    const trash = this._button(t.trash, () => this._memoryPage(++this._loadToken, true), deleted ? "primary" : "");
    filters.append(search, active, trash);
    const list = document.createElement("div");
    list.className = "grid";
    this._content.append(filters, list);

    const render = () => {
      const query = search.value.trim().toLocaleLowerCase();
      const shown = this._memories.filter(item =>
        JSON.stringify(item).toLocaleLowerCase().includes(query));
      list.replaceChildren();
      if (!shown.length) {
        const empty = document.createElement("div"); empty.className = "card"; empty.textContent = t.empty; list.append(empty);
        return;
      }
      for (const item of shown) {
        const card = document.createElement("article"); card.className = "card memory-card";
        const title = document.createElement("h2"); title.textContent = item.key;
        const meta = document.createElement("p"); meta.className = "meta";
        meta.textContent = `${item.category} · ${t.importance}: ${item.importance} · ${t.source}: ${item.source || "—"} · ${t.expires}: ${item.expires_at ? new Date(item.expires_at).toLocaleString() : t.never}`;
        const value = document.createElement("div"); value.className = "memory-value"; value.textContent = item.value;
        const actions = document.createElement("div"); actions.className = "actions";
        if (deleted) {
          actions.append(this._button(t.restore, async () => {
            await this._call("memory_restore", {key:item.key});
            await this._memoryPage(++this._loadToken, true);
          }));
        } else {
          actions.append(
            this._button(t.edit, () => this._memoryEditor(item, false)),
            this._button(t.remove, async () => {
              if (!confirm(t.deleteMemory)) return;
              await this._call("memory_delete", {key:item.key});
              await this._memoryPage(++this._loadToken, false);
            }, "danger")
          );
        }
        const references = document.createElement("div"); references.className = "entity-links";
        for (const reference of item.referenced_entities || []) {
          const chip = document.createElement(reference.verified && reference.home_assistant_path ? "a" : "span");
          chip.className = "entity-link" + (reference.verified ? " verified" : "");
          chip.textContent = `${reference.name || reference.entity_id} · ${reference.verified ? (reference.state || t.verified) : t.unverified}`;
          chip.title = reference.entity_id;
          if (chip.tagName === "A") {chip.href = reference.home_assistant_path; chip.target = "_top";}
          references.append(chip);
        }
        card.append(title, meta, value);
        if (references.childElementCount) card.append(references);
        card.append(actions); list.append(card);
      }
    };
    search.addEventListener("input", render);
    render();
  }

  _memoryEditor(item, deleted) {
    const t = this._labels();
    const card = document.createElement("form");
    card.className = "card editor-grid";
    const field = (placeholder, value = "", type = "text") => {
      const input = document.createElement("input"); input.type = type; input.placeholder = placeholder; input.value = value; return input;
    };
    const key = field(t.key, item?.key || ""); key.required = true; key.readOnly = Boolean(item);
    const category = field(t.category, item?.category || "fact"); category.required = true;
    const importance = field(t.importance, item?.importance || 5, "number"); importance.min = 1; importance.max = 10;
    const expires = field(t.expires, item?.expires_at ? item.expires_at.slice(0,16) : "", "datetime-local");
    const value = document.createElement("textarea"); value.className = "wide"; value.placeholder = t.value; value.required = true; value.value = item?.value || "";
    const actions = document.createElement("div"); actions.className = "actions wide";
    const save = document.createElement("button"); save.className = "primary"; save.textContent = t.save;
    actions.append(save, this._button(t.cancel, () => card.remove()));
    card.append(key, category, importance, expires, value, actions);
    this._content.insertBefore(card, this._content.children[1] || null);
    card.addEventListener("submit", async event => {
      event.preventDefault(); save.disabled = true;
      try {
        await this._call("memory_save", {
          key:key.value.trim(), value:value.value.trim(), category:category.value.trim(),
          importance:Number(importance.value),
          expires_at:expires.value ? new Date(expires.value).toISOString() : null,
        });
        await this._memoryPage(++this._loadToken, deleted);
      } catch (error) {
        save.disabled = false;
        alert(t.error + (error?.message || String(error)));
      }
    });
  }

  async _auditPage(token) {
    const t = this._labels();
    const events = await this._call("events");
    if (token !== this._loadToken) return;
    this._events = events;
    this._content.innerHTML = "";
    const refresh = this._button(t.refresh, () => this._auditPage(++this._loadToken));
    const exportButton = this._button(t.export, () => this._download("house-brain-audit.json", this._events));
    this._content.append(this._title("audit", [refresh, exportButton]));
    const filters = document.createElement("div"); filters.className = "card filters";
    const search = document.createElement("input"); search.type = "search"; search.placeholder = t.search; search.className = "grow";
    const mode = document.createElement("select");
    [["",t.allModes],["observe","observe"],["simulate","simulate"],["execute","execute"]].forEach(([value,label]) => {
      const option = document.createElement("option"); option.value = value; option.textContent = label; mode.append(option);
    });
    const status = document.createElement("select");
    const statuses = [...new Set(events.map(item => item.status).filter(Boolean))];
    [["",t.allStatuses],...statuses.map(value => [value,value])].forEach(([value,label]) => {
      const option = document.createElement("option"); option.value = value; option.textContent = label; status.append(option);
    });
    filters.append(search, mode, status);
    const insights = document.createElement("div"); insights.className = "insights";
    const list = document.createElement("div"); list.className = "page";
    this._content.append(filters, insights, list);
    const render = () => {
      const query = search.value.trim().toLocaleLowerCase();
      const shown = events.filter(item => (!mode.value || item.mode === mode.value) &&
        (!status.value || item.status === status.value) &&
        (!query || JSON.stringify(item).toLocaleLowerCase().includes(query)));
      const completed = shown.filter(item => item.status === "completed").length;
      insights.replaceChildren();
      [[t.total,shown.length],[t.completed,completed],[t.failed,shown.length-completed]].forEach(([label,value]) => {
        const card = document.createElement("div"); card.className = "card insight";
        const strong = document.createElement("strong"); strong.textContent = value;
        const span = document.createElement("span"); span.textContent = label; card.append(strong,span); insights.append(card);
      });
      list.replaceChildren();
      for (const item of shown) {
        const card = document.createElement("article"); card.className = "card";
        const title = document.createElement("h2"); title.textContent = `${item.event_type} · ${new Date(item.created_at).toLocaleString()}`;
        const badges = document.createElement("div");
        [item.mode,item.status].forEach(value => {const badge=document.createElement("span");badge.className=`badge ${value}`;badge.textContent=value;badges.append(badge);});
        const instruction = document.createElement("p"); instruction.className = "event-text"; instruction.textContent = `${t.instruction}: ${item.instruction || "—"}`;
        const response = document.createElement("p"); response.className = "event-text"; response.textContent = `${t.response}: ${item.response || "—"}`;
        const trace = item.tool_trace || [];
        const actionTrace = trace.filter(record => ["perform_action","perform_actions"].includes(record.tool));
        const requested = actionTrace.length ? actionTrace.map(record => {
          const args=record.arguments||{}, service=[args.domain,args.service].filter(Boolean).join(".");
          return `${args.entity_id || "unknown"}: ${service || record.tool}`;
        }).join("\n") : "—";
        const validation = actionTrace.length ? actionTrace.map(record =>
          record.error ? `${record.status}: ${record.error}` : record.status).join("\n") : "—";
        const haCall = actionTrace.some(record => record.outcome === "executed") ? "executed" : t.notCalled;
        const outcome = actionTrace.length ? actionTrace.map(record => record.outcome || record.status).join("\n") : (item.status || "—");
        const flow = document.createElement("div"); flow.className = "audit-flow";
        [[t.requested,requested],[t.validation,validation],[t.homeAssistantCall,haCall],[t.outcome,outcome]].forEach(([label,value]) => {
          const stage=document.createElement("div"), heading=document.createElement("strong"), body=document.createElement("span");
          stage.className="audit-stage"; heading.textContent=label; body.textContent=value; stage.append(heading,body); flow.append(stage);
        });
        const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = t.trace;
        const pre = document.createElement("pre"); pre.textContent = JSON.stringify(trace, null, 2); details.append(summary,pre);
        card.append(title,badges,instruction,response,flow,details); list.append(card);
      }
      if (!shown.length) {const empty=document.createElement("div");empty.className="card";empty.textContent=t.empty;list.append(empty);}
    };
    [search,mode,status].forEach(node => node.addEventListener("input",render)); render();
  }

  async _plansPage(token) {
    const t = this._labels();
    const plans = await this._call("plan_list");
    if (token !== this._loadToken) return;
    this._content.innerHTML = "";
    const refresh = this._button(t.refresh, () => this._plansPage(++this._loadToken));
    this._content.append(this._title("plans", [refresh]));

    const form = document.createElement("form"); form.className = "card";
    const instruction = document.createElement("textarea");
    instruction.placeholder = t.planInstruction; instruction.required = true; instruction.maxLength = 4000;
    const fields = document.createElement("div"); fields.className = "row";
    const policyCode = document.createElement("input");
    policyCode.type = "password"; policyCode.placeholder = t.policyCode; policyCode.autocomplete = "off";
    const haCode = document.createElement("input");
    haCode.type = "password"; haCode.placeholder = t.haCode; haCode.autocomplete = "off";
    fields.append(policyCode, haCode);
    const propose = document.createElement("button"); propose.className = "primary"; propose.textContent = t.proposePlan;
    const actions = document.createElement("div"); actions.className = "actions"; actions.append(propose);
    const setStatus = this._status(form);
    form.append(instruction, fields, actions);
    this._content.append(form);

    form.addEventListener("submit", async event => {
      event.preventDefault(); propose.disabled = true; setStatus(t.loading);
      try {
        await this._call("plan_propose", {
          instruction: instruction.value.trim(), policy_code: policyCode.value,
          home_assistant_code: haCode.value,
        });
        policyCode.value = ""; haCode.value = "";
        await this._plansPage(++this._loadToken);
      } catch (error) {
        setStatus(t.error + (error?.message || String(error)), true); propose.disabled = false;
      }
    });

    const list = document.createElement("div"); list.className = "page"; this._content.append(list);
    if (!plans.length) {const empty=document.createElement("div");empty.className="card";empty.textContent=t.empty;list.append(empty);return;}
    for (const plan of plans) {
      const card = document.createElement("article"); card.className = "card";
      const title = document.createElement("h2"); title.textContent = plan.plan_id.slice(0, 12);
      const badge = document.createElement("span"); badge.className = `badge ${plan.status}`; badge.textContent = plan.status;
      const meta = document.createElement("p"); meta.className = "meta"; meta.textContent = `${t.expires}: ${new Date(plan.expires_at).toLocaleString()}`;
      card.append(title, badge, meta);
      for (const item of plan.actions || []) {
        const action = document.createElement("div"); action.className = "audit-stage";
        const heading = document.createElement("strong"); heading.textContent = `${item.entity_id}: ${item.domain}.${item.service}`;
        const state = document.createElement("div"); state.textContent = `${t.initialState}: ${item.initial_state}`;
        const reason = document.createElement("div"); reason.className = "meta"; reason.textContent = item.reason;
        action.append(heading, state, reason); card.append(action);
      }
      if (plan.outcome?.length) {const pre=document.createElement("pre");pre.textContent=JSON.stringify(plan.outcome,null,2);card.append(pre);}
      if (plan.error) {const error=document.createElement("p");error.className="status error";error.textContent=plan.error;card.append(error);}
      if (plan.status === "proposed") {
        const controls = document.createElement("div"); controls.className = "actions";
        const approve = this._button(t.approvePlan, async () => {
          approve.disabled = true;
          try {
            await this._call("plan_approve", {plan_id:plan.plan_id,policy_code:policyCode.value,home_assistant_code:haCode.value});
            policyCode.value = ""; haCode.value = ""; await this._plansPage(++this._loadToken);
          } catch (error) {approve.disabled=false;alert(t.error+(error?.message||String(error)));}
        }, "primary");
        const reject = this._button(t.rejectPlan, async () => {
          await this._call("plan_reject", {plan_id:plan.plan_id}); await this._plansPage(++this._loadToken);
        }, "danger");
        controls.append(approve, reject); card.append(controls);
      }
      list.append(card);
    }
  }

  async _autonomyPage(token) {
    const t = this._labels();
    const payload = await this._call("autonomy_get");
    if (token !== this._loadToken) return;
    const visible = new Map(payload.configuration.visible.map(item => [item.entity_id,item]));
    const included = new Map(payload.configuration.include.map(item => [item.entity_id,item]));
    this._autonomyState = new Map(payload.entities.map(item => {
      const readable = visible.get(item.entity_id), controllable = included.get(item.entity_id);
      const configured = controllable || readable;
      return [item.entity_id, {
        item, mode:controllable ? "include" : readable ? "visible" : "hidden",
        name:configured?.name || item.friendly_name,
        code_required:Boolean(controllable?.code_required), code:"",
      }];
    }));
    this._content.innerHTML = "";
    const save = this._button(t.savePolicy, async () => {
      if (!confirm(t.confirmPolicy)) return;
      save.disabled = true;
      try {
        const values = [...this._autonomyState.entries()];
        const make = ([entity_id,state]) => ({entity_id,name:state.name || state.item.friendly_name});
        const visibleItems = values.filter(([,state]) => state.mode === "visible").map(make);
        const includeItems = values.filter(([,state]) => state.mode === "include").map(([entity_id,state]) => ({
          entity_id, name:state.name || state.item.friendly_name,
          code_required:state.code_required, code:state.code || null,
        }));
        await this._call("autonomy_update", {visible:visibleItems,include:includeItems});
        setStatus(t.saved);
        for (const state of this._autonomyState.values()) state.code = "";
      } catch (error) {
        setStatus(t.error + (error?.message || String(error)), true);
      } finally { save.disabled = false; }
    }, "primary");
    this._content.append(this._title("autonomy", [save]));
    const filters = document.createElement("div"); filters.className = "card filters";
    const search = document.createElement("input"); search.type = "search"; search.placeholder = t.search; search.className = "grow";
    const domain = document.createElement("select");
    const first = document.createElement("option"); first.value = ""; first.textContent = t.domain; domain.append(first);
    [...new Set(payload.entities.map(item => item.domain))].sort().forEach(value => {
      const option = document.createElement("option"); option.value=value; option.textContent=value; domain.append(option);
    });
    filters.append(search,domain);
    const statusCard = document.createElement("div"); statusCard.className = "status";
    const setStatus = (message,error=false) => {statusCard.textContent=message;statusCard.classList.toggle("error",error);};
    const list = document.createElement("div"); list.className = "page";
    this._content.append(filters,statusCard,list);
    const render = () => {
      const query=search.value.trim().toLocaleLowerCase(), selected=domain.value;
      const states=[...this._autonomyState.values()].filter(state =>
        (!selected || state.item.domain === selected) &&
        (!query || `${state.item.entity_id} ${state.item.friendly_name} ${state.name} ${state.item.area_name || ""} ${state.item.device_name || ""}`.toLocaleLowerCase().includes(query)));
      list.replaceChildren();
      const fragment=document.createDocumentFragment();
      for (const state of states) {
        const row=document.createElement("article");row.className="card entity";
        const identity=document.createElement("div");
        const entityId=document.createElement("div");entityId.className="entity-id";entityId.textContent=state.item.entity_id;
        const entityState=document.createElement("div");entityState.className="entity-state";entityState.textContent=[state.item.friendly_name,state.item.state,state.item.area_name,state.item.device_name].filter(Boolean).join(" · ");
        identity.append(entityId,entityState);
        const name=document.createElement("input");name.placeholder=t.entityName;name.value=state.name||"";
        name.disabled=state.mode==="hidden";name.addEventListener("input",()=>{state.name=name.value;});
        const mode=document.createElement("select");
        [["hidden",t.notVisible],["visible",t.visible],["include",t.controllable]].forEach(([value,label])=>{
          const option=document.createElement("option");option.value=value;option.textContent=label;mode.append(option);
        });
        mode.value=state.mode;
        const codeBox=document.createElement("div");codeBox.className="code-box";
        const codeRequired=document.createElement("input");codeRequired.type="checkbox";codeRequired.checked=state.code_required;
        const codeLabel=document.createElement("label");codeLabel.append(codeRequired,document.createTextNode(" "+t.codeRequired));
        const code=document.createElement("input");code.type="password";code.placeholder=t.newCode;code.value=state.code;
        const update=()=>{state.mode=mode.value;name.disabled=state.mode==="hidden";codeRequired.disabled=state.mode!=="include";code.disabled=state.mode!=="include"||!codeRequired.checked;if(state.mode!=="include"){state.code_required=false;codeRequired.checked=false;state.code="";code.value="";}};
        mode.addEventListener("change",update);codeRequired.addEventListener("change",()=>{state.code_required=codeRequired.checked;update();});
        code.addEventListener("input",()=>{state.code=code.value;});codeBox.append(codeLabel,code);update();
        row.append(identity,name,mode,codeBox);fragment.append(row);
      }
      list.append(fragment);
      if (!states.length) {const empty=document.createElement("div");empty.className="card";empty.textContent=t.empty;list.append(empty);}
    };
    search.addEventListener("input",render);domain.addEventListener("change",render);render();
  }

  async _contextPage(token) {
    const t=this._labels(),payload=await this._call("context_views_get");
    if(token!==this._loadToken)return;
    const state=payload.configuration;
    this._content.innerHTML="";
    const save=this._button(t.save,async()=>{
      save.disabled=true;setStatus("");
      try{const result=await this._call("context_views_update",state);Object.assign(state,result.configuration);setStatus(t.saved);render();}
      catch(error){setStatus(t.error+(error?.message||String(error)),true)}
      finally{save.disabled=false}
    },"primary");
    const add=this._button(t.contextAdd,()=>{
      let number=state.views.length+1,id=`context_view_${number}`;
      while(state.views.some(view=>view.id===id))id=`context_view_${++number}`;
      state.views.push({id,name:`Context view ${number}`,enabled:true,areas:[],domains:[],entities:[],max_entities:50,include_linked_memories:true});render();
    });
    this._content.append(this._title("context",[add,save]));
    const notice=document.createElement("div");notice.className="card status";notice.textContent=t.contextPolicy;
    const controls=document.createElement("div");controls.className="card";
    const defaultLabel=document.createElement("label");defaultLabel.textContent=t.contextDefault;
    const defaultSelect=document.createElement("select");defaultLabel.append(defaultSelect);controls.append(defaultLabel);
    const status=document.createElement("div");status.className="status";
    const setStatus=(message,error=false)=>{status.textContent=message;status.classList.toggle("error",error)};
    const list=document.createElement("div");list.className="page";
    this._content.append(notice,controls,status,list);
    const values=value=>[...new Set(String(value).split(",").map(item=>item.trim()).filter(Boolean))];
    const input=(label,value,onchange,type="text")=>{const wrapper=document.createElement("label");wrapper.textContent=label;const node=document.createElement("input");node.type=type;node.value=value;node.addEventListener("change",()=>onchange(node));wrapper.append(node);return wrapper};
    const render=()=>{
      defaultSelect.replaceChildren(new Option(t.contextNone,""));
      for(const view of state.views)defaultSelect.add(new Option(`${view.name} (${view.id})`,view.id));
      defaultSelect.value=state.default_view||"";defaultSelect.onchange=()=>{state.default_view=defaultSelect.value||null};
      list.replaceChildren();
      state.views.forEach((view,index)=>{
        const card=document.createElement("article");card.className="card";
        const grid=document.createElement("div");grid.className="editor-grid";
        grid.append(
          input(t.entityName,view.name,node=>{view.name=node.value.trim()}),
          input("ID",view.id,node=>{view.id=node.value.trim().toLowerCase()}),
          input(t.contextAreas,(view.areas||[]).join(", "),node=>{view.areas=values(node.value)}),
          input(t.contextDomains,(view.domains||[]).join(", "),node=>{view.domains=values(node.value).map(x=>x.toLowerCase())}),
          input(t.contextEntities,(view.entities||[]).join(", "),node=>{view.entities=values(node.value).map(x=>x.toLowerCase())}),
          input(t.contextLimit,view.max_entities||50,node=>{view.max_entities=Number(node.value)||50},"number")
        );
        const enabled=document.createElement("input");enabled.type="checkbox";enabled.checked=view.enabled!==false;enabled.onchange=()=>{view.enabled=enabled.checked};
        const enabledLabel=document.createElement("label");enabledLabel.append(enabled,document.createTextNode(" "+t.contextEnabled));
        const memories=document.createElement("input");memories.type="checkbox";memories.checked=view.include_linked_memories!==false;memories.onchange=()=>{view.include_linked_memories=memories.checked};
        const memoriesLabel=document.createElement("label");memoriesLabel.append(memories,document.createTextNode(" "+t.contextMemories));
        const preview=document.createElement("div");preview.className="status";
        const previewButton=this._button(t.contextPreview,async()=>{preview.textContent=t.loading;try{const result=await this._call("context_views_preview",{view_id:view.id});preview.textContent=`${result.selected_before_limit} ${t.contextSelected}, ${result.omitted_by_view_limit} ${t.contextOmitted}`}catch(error){preview.textContent=t.error+(error?.message||String(error))}});
        const remove=this._button(t.contextRemove,()=>{state.views.splice(index,1);if(state.default_view===view.id)state.default_view=null;render()},"danger");
        const actions=document.createElement("div");actions.className="row";actions.append(enabledLabel,memoriesLabel,previewButton,remove);
        card.append(grid,actions,preview);list.append(card);
      });
      if(!state.views.length){const empty=document.createElement("div");empty.className="card";empty.textContent=t.empty;list.append(empty)}
    };
    render();
  }

  async _logsPage(token) {
    const t = this._labels();
    this._content.innerHTML = "";
    const refresh = this._button(t.refresh, () => load());
    this._content.append(this._title("logs", [refresh]));
    const filters=document.createElement("div");filters.className="card filters";
    const search=document.createElement("input");search.type="search";search.placeholder=t.search;search.className="grow";
    const level=document.createElement("select");
    [["",t.level],["INFO","INFO"],["WARNING","WARNING"],["ERROR","ERROR"],["CRITICAL","CRITICAL"]].forEach(([value,label])=>{const option=document.createElement("option");option.value=value;option.textContent=label;level.append(option);});
    const automatic=document.createElement("input");automatic.type="checkbox";automatic.checked=true;
    const autoLabel=document.createElement("label");autoLabel.append(automatic,document.createTextNode(" "+t.automatic));
    filters.append(search,level,autoLabel);
    const status=document.createElement("div");status.className="status";
    const list=document.createElement("div");list.className="page";
    this._content.append(filters,status,list);
    const load=async()=>{
      status.textContent=t.loading;
      try{
        const items=await this._call("logs",{query:search.value.trim(),level:level.value});
        if(token!==this._loadToken)return;
        list.replaceChildren();
        for(const item of [...items].reverse()){
          const row=document.createElement("article");row.className="card log-entry";
          const time=document.createElement("span");time.textContent=new Date(item.timestamp).toLocaleString();
          const severity=document.createElement("strong");severity.className=item.level;severity.textContent=item.level;
          const source=document.createElement("span");source.className="meta";source.textContent=`${item.module}.${item.function}`;
          const message=document.createElement("span");message.className="log-message";message.textContent=item.message;
          row.append(time,severity,source,message);list.append(row);
        }
        if(!items.length){const empty=document.createElement("div");empty.className="card";empty.textContent=t.empty;list.append(empty);}
        status.textContent="";
      }catch(error){status.textContent=t.error+(error?.message||String(error));status.className="status error";}
    };
    let debounce;
    search.addEventListener("input",()=>{clearTimeout(debounce);debounce=setTimeout(load,250);});
    level.addEventListener("change",load);
    automatic.addEventListener("change",()=>{this._stopLogTimer();if(automatic.checked)this._logTimer=setInterval(load,5000);});
    await load();
    if(automatic.checked)this._logTimer=setInterval(load,5000);
  }

  _stopLogTimer() {
    if (this._logTimer) clearInterval(this._logTimer);
    this._logTimer = null;
  }

  async _installationPage(token) {
    const t=this._labels();
    const report=await this._call("installation_status");
    if(token!==this._loadToken)return;
    this._content.innerHTML="";
    const refresh=this._button(t.refresh,()=>this._installationPage(++this._loadToken));
    this._content.append(this._title("installation",[refresh]));
    const summary=document.createElement("section");
    summary.className=`card summary-line ${report.status==="ready"?"":"degraded"}`;
    const dot=document.createElement("span");dot.className="dot";
    const label=document.createElement("strong");
    label.textContent=report.status==="ready"?t.healthy:t.degraded;
    summary.append(dot,label);
    const grid=document.createElement("div");grid.className="grid";
    [
      [t.installationState,report],
      [t.persistence,{root:report.persistent_root,access:report.persistent_root_access,policy:report.policy,database:report.database}],
      [t.lifecycleSafety,{automatic_updates:report.automatic_updates,container_restart_control:report.container_restart_control,note:t.lifecycleSafety}],
    ].forEach(([title,data])=>{
      const card=document.createElement("article");card.className="card";
      const heading=document.createElement("h2");heading.textContent=title;
      const pre=document.createElement("pre");pre.textContent=JSON.stringify(data,null,2);
      card.append(heading,pre);grid.append(card);
    });
    this._content.append(summary,grid);
  }

  async _diagnosticsPage(token) {
    const t=this._labels();
    const report=await this._call("diagnostics");
    if(token!==this._loadToken)return;
    this._content.innerHTML="";
    const refresh=this._button(t.refresh,()=>this._diagnosticsPage(++this._loadToken));
    const download=this._button(t.download,()=>this._download("house-brain-diagnostics.json",report));
    this._content.append(this._title("diagnostics",[refresh,download]));
    const summary=document.createElement("section");summary.className=`card summary-line ${report.status==="ok"?"":"degraded"}`;
    const dot=document.createElement("span");dot.className="dot";
    const label=document.createElement("strong");label.textContent=report.status==="ok"?t.healthy:t.degraded;summary.append(dot,label);
    const grid=document.createElement("div");grid.className="grid";
    [[t.homeAssistant,report.home_assistant],[t.llm,report.llm],[t.providerMetrics,report.provider_metrics || {}],[t.persistence,report.persistence]].forEach(([title,data])=>{
      const card=document.createElement("article");card.className="card";
      const heading=document.createElement("h2");heading.textContent=title;
      const pre=document.createElement("pre");pre.textContent=JSON.stringify(data,null,2);card.append(heading,pre);grid.append(card);
    });
    this._content.append(summary,grid);
  }
}

if (!customElements.get("house-brain-panel")) {
  customElements.define("house-brain-panel", HouseBrainPanel);
}

