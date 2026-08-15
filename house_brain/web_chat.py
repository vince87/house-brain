import json

from fastapi.responses import HTMLResponse

from house_brain.languages import language_family, localized_ui_messages

CHAT_HTML = r"""<!doctype html>
<html lang="__LANG__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>House Brain</title>
  <style>
    :root {
      --bg: #08100d;
      --panel: #101a16;
      --panel-2: #17231e;
      --line: #293a32;
      --text: #edf7f1;
      --muted: #9db0a6;
      --accent: #62d99b;
      --accent-strong: #30b879;
      --danger: #ff8a80;
      --shadow: 0 24px 70px rgba(0, 0, 0, .35);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 15% 10%, rgba(48, 184, 121, .14), transparent 28rem),
        var(--bg);
      color: var(--text);
      font: 16px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
    }
    button, input, textarea { font: inherit; }
    button { cursor: pointer; }
    .shell {
      width: min(960px, 100%);
      min-height: 100vh;
      margin: 0 auto;
      padding: 20px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 16px;
    }
    header, .card {
      border: 1px solid var(--line);
      background: rgba(16, 26, 22, .92);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }
    header {
      min-height: 68px;
      padding: 12px 16px;
      border-radius: 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }
    .brand { display: flex; align-items: center; gap: 12px; }
    .mark {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      display: grid;
      place-items: center;
      background: linear-gradient(145deg, var(--accent), var(--accent-strong));
      color: #06110c;
      font-weight: 900;
    }
    h1 { margin: 0; font-size: 1.05rem; }
    .subtitle, .status, .meta { color: var(--muted); font-size: .82rem; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .btn {
      min-height: 40px;
      padding: 8px 13px;
      border: 1px solid var(--line);
      border-radius: 11px;
      color: var(--text);
      background: var(--panel-2);
    }
    .btn:hover { border-color: var(--accent); }
    .btn.primary {
      border-color: transparent;
      background: var(--accent);
      color: #06110c;
      font-weight: 750;
    }
    .btn:disabled { opacity: .5; cursor: not-allowed; }
    main { min-height: 0; }
    .card { border-radius: 22px; overflow: hidden; }
    .auth {
      width: min(460px, 100%);
      margin: 9vh auto 0;
      padding: 28px;
    }
    .auth h2 { margin: 0 0 8px; }
    .auth p { color: var(--muted); margin: 0 0 20px; }
    label { display: block; margin-bottom: 7px; color: var(--muted); font-size: .9rem; }
    .auth-row { display: grid; grid-template-columns: 1fr auto; gap: 9px; }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #0b1410;
      color: var(--text);
      outline: none;
    }
    input { min-height: 44px; padding: 10px 12px; }
    input:focus, textarea:focus { border-color: var(--accent); }
    .error { min-height: 1.5em; margin-top: 12px; color: var(--danger); }
    .chat {
      height: calc(100vh - 124px);
      min-height: 520px;
      display: grid;
      grid-template-rows: 1fr auto;
    }
    .messages {
      overflow-y: auto;
      padding: 24px;
      scroll-behavior: smooth;
    }
    .empty {
      height: 100%;
      display: grid;
      place-items: center;
      text-align: center;
      color: var(--muted);
    }
    .message {
      width: fit-content;
      max-width: min(78%, 720px);
      margin: 0 0 16px;
      padding: 12px 15px;
      border: 1px solid var(--line);
      border-radius: 16px 16px 16px 5px;
      background: var(--panel-2);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .message.user {
      margin-left: auto;
      border-color: rgba(98, 217, 155, .28);
      border-radius: 16px 16px 5px 16px;
      background: rgba(48, 184, 121, .16);
    }
    .message.pending { color: var(--muted); }
    .meta { margin-top: 7px; }
    .message a { color: var(--accent); text-underline-offset: 3px; }
    .composer {
      padding: 14px;
      border-top: 1px solid var(--line);
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      background: rgba(8, 16, 13, .65);
    }
    textarea {
      min-height: 48px;
      max-height: 180px;
      resize: none;
      padding: 12px 14px;
    }
    .send { min-width: 94px; }
    [hidden] { display: none !important; }
    @media (max-width: 640px) {
      .shell { padding: 10px; }
      header { align-items: flex-start; }
      .subtitle { display: none; }
      .chat { height: calc(100vh - 98px); min-height: 430px; }
      .messages { padding: 15px; }
      .message { max-width: 91%; }
      .composer { grid-template-columns: 1fr; }
      .send { width: 100%; }
      .auth-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div class="brand">
        <div class="mark">HB</div>
        <div>
          <h1>House Brain</h1>
          <div class="subtitle">__SUBTITLE__</div>
        </div>
      </div>
      <div class="actions" id="chatActions" hidden>
        <span class="status" id="sessionLabel"></span>
        <button class="btn" id="newChat" type="button">__NEW__</button>
        <button class="btn" id="resetChat" type="button">__DELETE__</button>
        <button class="btn" id="logout" type="button">__LOGOUT__</button>
      </div>
    </header>

    <main>
      <section class="card auth" id="authPanel">
        <h2>__LOGIN__</h2>
        <p>__INTRO__</p>
        <form id="authForm">
          <label for="apiKey">__API_KEY__</label>
          <div class="auth-row">
            <input id="apiKey" type="password" autocomplete="off" required>
            <button class="btn primary" id="loginButton" type="submit">
              __LOGIN__
            </button>
          </div>
          <div class="error" id="authError" role="alert"></div>
        </form>
      </section>

      <section class="card chat" id="chatPanel" hidden>
        <div class="messages" id="messages" aria-live="polite">
          <div class="empty" id="emptyState">__EMPTY__</div>
        </div>
        <form class="composer" id="chatForm">
          <textarea
            id="messageInput"
            maxlength="4000"
            placeholder="__PLACEHOLDER__"
            required
          ></textarea>
          <button class="btn primary send" id="sendButton" type="submit">
            __SEND__
          </button>
        </form>
      </section>
    </main>
  </div>

  <script>
    (() => {
      "use strict";

      const KEY_NAME = "house_brain_api_key";
      const SESSION_NAME = "house_brain_chat_session";
      const i18n = __I18N__;
      const authPanel = document.getElementById("authPanel");
      const chatPanel = document.getElementById("chatPanel");
      const chatActions = document.getElementById("chatActions");
      const authForm = document.getElementById("authForm");
      const apiKeyInput = document.getElementById("apiKey");
      const authError = document.getElementById("authError");
      const loginButton = document.getElementById("loginButton");
      const chatForm = document.getElementById("chatForm");
      const messageInput = document.getElementById("messageInput");
      const sendButton = document.getElementById("sendButton");
      const messages = document.getElementById("messages");
      const emptyState = document.getElementById("emptyState");
      const sessionLabel = document.getElementById("sessionLabel");

      function newSessionId() {
        const suffix = crypto.randomUUID
          ? crypto.randomUUID()
          : Date.now().toString(36) + Math.random().toString(36).slice(2);
        return ("web-" + suffix).slice(0, 64);
      }

      function sessionId() {
        let value = sessionStorage.getItem(SESSION_NAME);
        if (!value) {
          value = newSessionId();
          sessionStorage.setItem(SESSION_NAME, value);
        }
        return value;
      }

      function apiKey() {
        return sessionStorage.getItem(KEY_NAME) || "";
      }

      async function api(path, options = {}) {
        const headers = new Headers(options.headers || {});
        headers.set("X-API-Key", apiKey());
        if (options.body) headers.set("Content-Type", "application/json");
        const response = await fetch(path, {...options, headers});
        if (response.status === 401) {
          showLogin(i18n.invalid_key);
          throw new Error(i18n.invalid_auth);
        }
        return response;
      }

      function showLogin(error = "") {
        sessionStorage.removeItem(KEY_NAME);
        authError.textContent = error;
        authPanel.hidden = false;
        chatPanel.hidden = true;
        chatActions.hidden = true;
        apiKeyInput.value = "";
        apiKeyInput.focus();
      }

      function showChat() {
        authPanel.hidden = true;
        chatPanel.hidden = false;
        chatActions.hidden = false;
        sessionLabel.textContent = sessionId();
        messageInput.focus();
      }

      function clearMessages() {
        for (const item of messages.querySelectorAll(".message")) item.remove();
        emptyState.hidden = false;
      }

      function appendTextWithLinks(container, content) {
        content = content.replaceAll("**", "");
        const pattern = /https?:\/\/[^\s<>"']+/g;
        let cursor = 0;
        for (const match of content.matchAll(pattern)) {
          container.appendChild(
            document.createTextNode(content.slice(cursor, match.index))
          );
          const raw = match[0];
          const url = raw.replace(/[),.;]+$/, "");
          const suffix = raw.slice(url.length);
          const link = document.createElement("a");
          link.href = url;
          link.textContent = url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          container.appendChild(link);
          if (suffix) container.appendChild(document.createTextNode(suffix));
          cursor = match.index + raw.length;
        }
        container.appendChild(
          document.createTextNode(content.slice(cursor))
        );
      }

      function addMessage(role, content, meta = "") {
        emptyState.hidden = true;
        const item = document.createElement("article");
        item.className = "message " + role;
        const text = document.createElement("div");
        appendTextWithLinks(text, content);
        item.appendChild(text);
        if (meta) {
          const details = document.createElement("div");
          details.className = "meta";
          details.textContent = meta;
          item.appendChild(details);
        }
        messages.appendChild(item);
        messages.scrollTop = messages.scrollHeight;
        return item;
      }

      async function loadHistory() {
        clearMessages();
        const path = "/conversations/"
          + encodeURIComponent(sessionId())
          + "?limit=100";
        const response = await api(path);
        if (!response.ok) throw new Error(i18n.load_error);
        const history = await response.json();
        for (const item of history) addMessage(item.role, item.content);
      }

      async function authenticate(key) {
        loginButton.disabled = true;
        authError.textContent = "";
        sessionStorage.setItem(KEY_NAME, key);
        try {
          const response = await api("/auth/check");
          if (!response.ok) throw new Error(i18n.login_error);
          showChat();
          await loadHistory();
        } catch (error) {
          if (apiKey()) showLogin(error.message);
        } finally {
          loginButton.disabled = false;
        }
      }

      authForm.addEventListener("submit", (event) => {
        event.preventDefault();
        authenticate(apiKeyInput.value);
      });

      chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        addMessage("user", message);
        messageInput.value = "";
        messageInput.style.height = "";
        sendButton.disabled = true;
        messageInput.disabled = true;
        const pending = addMessage("pending", i18n.thinking);

        try {
          const response = await api("/agent/chat", {
            method: "POST",
            body: JSON.stringify({message, session_id: sessionId()})
          });
          const payload = await response.json();
          pending.remove();
          if (!response.ok) {
            const detail = typeof payload.detail === "string"
              ? payload.detail
              : i18n.request_error;
            throw new Error(detail);
          }
          const used = payload.tools_used && payload.tools_used.length
            ? i18n.tools + payload.tools_used.join(", ")
            : "";
          addMessage("assistant", payload.response, used);
        } catch (error) {
          pending.remove();
          if (apiKey()) addMessage("assistant", i18n.error + error.message);
        } finally {
          sendButton.disabled = false;
          messageInput.disabled = false;
          messageInput.focus();
        }
      });

      messageInput.addEventListener("input", () => {
        messageInput.style.height = "auto";
        messageInput.style.height = Math.min(messageInput.scrollHeight, 180) + "px";
      });

      messageInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          chatForm.requestSubmit();
        }
      });

      document.getElementById("newChat").addEventListener("click", () => {
        sessionStorage.setItem(SESSION_NAME, newSessionId());
        sessionLabel.textContent = sessionId();
        clearMessages();
        messageInput.focus();
      });

      document.getElementById("resetChat").addEventListener("click", async () => {
        if (!confirm(i18n.confirm_delete)) return;
        try {
          const path = "/conversations/" + encodeURIComponent(sessionId());
          const response = await api(path, {method: "DELETE"});
          if (!response.ok) throw new Error(i18n.delete_error);
          clearMessages();
        } catch (error) {
          if (apiKey()) addMessage("assistant", i18n.error + error.message);
        }
      });

      document.getElementById("logout").addEventListener("click", () => showLogin());

      if (apiKey()) authenticate(apiKey());
      else showLogin();
    })();
  </script>
</body>
</html>
"""


def chat_page(language: str = "it") -> HTMLResponse:
    """Return the local, dependency-free chat client with strict browser headers."""
    return HTMLResponse(
        _localized_chat_html(language),
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; "
                "style-src 'unsafe-inline'; "
                "script-src 'unsafe-inline'; "
                "connect-src 'self'; "
                "img-src 'self' data:; "
                "base-uri 'none'; "
                "form-action 'self'; "
                "frame-ancestors 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


def _localized_chat_html(language: str) -> str:
    messages = localized_ui_messages(language)
    replacements = {
        "__LANG__": language_family(language),
        "__SUBTITLE__": messages["subtitle"],
        "__NEW__": messages["new"],
        "__DELETE__": messages["delete"],
        "__LOGOUT__": messages["logout"],
        "__LOGIN__": messages["login"],
        "__INTRO__": messages["intro"],
        "__API_KEY__": messages["api_key"],
        "__EMPTY__": messages["empty"],
        "__PLACEHOLDER__": messages["placeholder"],
        "__SEND__": messages["send"],
        "__I18N__": json.dumps(messages, ensure_ascii=True).replace("<", "\\u003c"),
    }
    html = CHAT_HTML
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html
