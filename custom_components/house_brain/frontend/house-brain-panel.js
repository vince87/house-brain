const SECTIONS = [
  ["chat", "/chat"],
  ["memories", "/memories"],
  ["audit", "/audit"],
  ["autonomy", "/autonomy"],
  ["logs", "/logs"],
  ["diagnostics", "/system"],
];

const LABELS = {
  en: {
    chat: "Chat",
    memories: "Memories",
    audit: "Audit",
    autonomy: "Autonomy",
    logs: "Logs",
    diagnostics: "Diagnostics",
    open: "Open in new tab",
    loading: "Loading House Brain…",
    invalid: "The configured House Brain URL is not valid.",
  },
  it: {
    chat: "Chat",
    memories: "Memorie",
    audit: "Audit",
    autonomy: "Autonomia",
    logs: "Log",
    diagnostics: "Diagnostica",
    open: "Apri in una nuova scheda",
    loading: "Caricamento di House Brain…",
    invalid: "L'URL configurato per House Brain non è valido.",
  },
};

class HouseBrainPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._section = "chat";
    this._onHashChange = () => this._selectFromHash();
  }

  set hass(value) {
    this._hass = value;
    this._render();
  }

  set panel(value) {
    this._panel = value;
    this._render();
  }

  set narrow(value) {
    this.toggleAttribute("narrow", Boolean(value));
  }

  connectedCallback() {
    window.addEventListener("hashchange", this._onHashChange);
    this._selectFromHash();
    this._render();
  }

  disconnectedCallback() {
    window.removeEventListener("hashchange", this._onHashChange);
  }

  _language() {
    const language = this._hass?.language || "en";
    return LABELS[language.split("-")[0]] || LABELS.en;
  }

  _baseUrl() {
    const configured = this._panel?.config?.base_url;
    try {
      const url = new URL(configured);
      if (!["http:", "https:"].includes(url.protocol)) {
        return null;
      }
      url.pathname = url.pathname.replace(/\/$/, "");
      url.search = "";
      url.hash = "";
      return url;
    } catch {
      return null;
    }
  }

  _selectFromHash() {
    const requested = window.location.hash.slice(1);
    if (SECTIONS.some(([key]) => key === requested)) {
      this._section = requested;
    }
  }

  _navigate(section) {
    this._section = section;
    window.history.replaceState(null, "", `#${section}`);
    this._render();
  }

  _pageUrl() {
    const base = this._baseUrl();
    const section = SECTIONS.find(([key]) => key === this._section);
    if (!base || !section) {
      return null;
    }
    return new URL(section[1], `${base.origin}/`).href;
  }

  _render() {
    if (!this.isConnected || !this._panel) {
      return;
    }
    const labels = this._language();
    const pageUrl = this._pageUrl();
    const buttons = SECTIONS.map(([key]) => {
      const active = key === this._section ? "active" : "";
      return `<button class="${active}" data-section="${key}" type="button">
        ${labels[key] || LABELS.en[key]}
      </button>`;
    }).join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          min-height: 0;
          color: var(--primary-text-color);
          background: var(--primary-background-color);
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
        }
        .panel {
          height: 100%;
          min-height: 0;
          display: grid;
          grid-template-rows: auto 1fr;
          background: var(--primary-background-color);
        }
        .toolbar {
          min-height: 64px;
          padding: 0 16px;
          display: flex;
          align-items: center;
          gap: 14px;
          border-bottom: 1px solid var(--divider-color);
          background: var(--card-background-color);
          box-shadow: 0 1px 3px rgba(0, 0, 0, .12);
          z-index: 1;
        }
        .brand {
          display: flex;
          align-items: center;
          gap: 10px;
          white-space: nowrap;
          font-size: 1.05rem;
          font-weight: 500;
        }
        .mark {
          width: 38px;
          height: 38px;
          display: grid;
          place-items: center;
          border-radius: 10px;
          color: white;
          background: var(--primary-color, #03a9f4);
          font-size: .8rem;
          font-weight: 800;
        }
        nav {
          min-width: 0;
          flex: 1;
          align-self: stretch;
          display: flex;
          overflow-x: auto;
          scrollbar-width: none;
        }
        nav::-webkit-scrollbar { display: none; }
        button {
          min-width: max-content;
          padding: 0 14px;
          border: 0;
          border-bottom: 3px solid transparent;
          color: var(--secondary-text-color);
          background: transparent;
          font: inherit;
          cursor: pointer;
        }
        button:hover {
          color: var(--primary-text-color);
          background: color-mix(in srgb, var(--primary-color, #03a9f4) 10%, transparent);
        }
        button.active {
          color: var(--primary-color, #03a9f4);
          border-bottom-color: var(--primary-color, #03a9f4);
        }
        .external {
          min-width: max-content;
          color: var(--primary-color, #03a9f4);
          text-decoration: none;
          font-size: .86rem;
        }
        .content {
          min-height: 0;
          position: relative;
        }
        iframe {
          width: 100%;
          height: 100%;
          border: 0;
          background: var(--primary-background-color);
        }
        .message {
          height: 100%;
          display: grid;
          place-items: center;
          padding: 24px;
          color: var(--secondary-text-color);
          text-align: center;
        }
        :host([narrow]) .toolbar {
          padding: 0 8px;
          gap: 8px;
        }
        :host([narrow]) .brand span:last-child,
        :host([narrow]) .external span {
          display: none;
        }
        :host([narrow]) .mark {
          width: 36px;
          height: 36px;
        }
        :host([narrow]) button {
          padding: 0 10px;
          font-size: .82rem;
        }
      </style>
      <section class="panel">
        <header class="toolbar">
          <div class="brand"><span class="mark">HB</span><span>House Brain</span></div>
          <nav aria-label="House Brain">${buttons}</nav>
          ${pageUrl ? `<a class="external" href="${pageUrl}" target="_blank"
            rel="noopener noreferrer" title="${labels.open}">
            ↗ <span>${labels.open}</span>
          </a>` : ""}
        </header>
        <div class="content">
          ${pageUrl
            ? `<iframe src="${pageUrl}" title="House Brain"
                referrerpolicy="no-referrer"></iframe>`
            : `<div class="message">${labels.invalid}</div>`}
        </div>
      </section>
    `;

    this.shadowRoot.querySelectorAll("button[data-section]").forEach((button) => {
      button.addEventListener("click", () => this._navigate(button.dataset.section));
    });
  }
}

if (!customElements.get("house-brain-panel")) {
  customElements.define("house-brain-panel", HouseBrainPanel);
}
