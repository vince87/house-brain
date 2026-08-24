"""Shared Home Assistant-inspired theme for House Brain web interfaces."""

from urllib.parse import urlsplit

from house_brain.languages import language_family

_NAVIGATION_LABELS = {
    "ar": (
        "المحادثة",
        "الذكريات",
        "التدقيق",
        "الخطط",
        "الاستقلالية",
        "السجلات",
        "التشخيص",
        "التثبيت",
    ),
    "de": (
        "Chat",
        "Erinnerungen",
        "Audit",
        "Aktionspläne",
        "Autonomie",
        "Protokolle",
        "Diagnose",
        "Installation",
    ),
    "en": (
        "Chat",
        "Memories",
        "Audit",
        "Action plans",
        "Autonomy",
        "Logs",
        "Diagnostics",
        "Installation",
    ),
    "es": (
        "Chat",
        "Memorias",
        "Auditoría",
        "Planes",
        "Autonomía",
        "Registros",
        "Diagnóstico",
        "Instalación",
    ),
    "fr": (
        "Chat",
        "Mémoires",
        "Audit",
        "Plans",
        "Autonomie",
        "Journaux",
        "Diagnostic",
        "Installation",
    ),
    "it": (
        "Chat",
        "Memorie",
        "Audit",
        "Piani",
        "Autonomia",
        "Log",
        "Diagnostica",
        "Installazione",
    ),
    "ja": (
        "チャット",
        "メモリ",
        "監査",
        "計画",
        "自律性",
        "ログ",
        "診断",
        "インストール",
    ),
    "ko": ("채팅", "메모리", "감사", "계획", "자율성", "로그", "진단", "설치"),
    "pt": (
        "Chat",
        "Memórias",
        "Auditoria",
        "Planos",
        "Autonomia",
        "Logs",
        "Diagnóstico",
        "Instalação",
    ),
    "zh": ("聊天", "记忆", "审计", "计划", "自主", "日志", "诊断", "安装"),
}


def shared_navigation(active: str, language: str) -> str:
    """Render the localized application bar and management navigation."""
    labels = _NAVIGATION_LABELS.get(language_family(language), _NAVIGATION_LABELS["en"])
    destinations = (
        ("chat", "/chat", labels[0]),
        ("memories", "/memories", labels[1]),
        ("audit", "/audit", labels[2]),
        ("plans", "/plans", labels[3]),
        ("autonomy", "/autonomy", labels[4]),
        ("logs", "/logs", labels[5]),
        ("diagnostics", "/system", labels[6]),
        ("installation", "/installation", labels[7]),
    )
    links = "".join(
        f'<a href="{href}" class="hb-nav-link'
        f'{" active" if key == active else ""}"'
        f"{' aria-current="page"' if key == active else ''}>{label}</a>"
        for key, href, label in destinations
    )
    return (
        '<nav class="hb-nav" aria-label="House Brain">'
        '<a class="hb-nav-brand" href="/chat" aria-label="House Brain">'
        '<span class="hb-nav-mark">HB</span><strong>House Brain</strong></a>'
        f'<div class="hb-nav-links">{links}</div></nav>'
        "<script>if(window.self!==window.top){"
        'document.documentElement.classList.add("hb-embedded")}</script>'
    )


def browser_security_headers(
    frame_ancestor: str | None = None,
) -> dict[str, str]:
    """Return strict browser headers, optionally allowing the configured HA origin."""
    headers = {
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }
    if frame_ancestor is None:
        ancestor_policy = "'none'"
        headers["X-Frame-Options"] = "DENY"
    else:
        parsed = urlsplit(frame_ancestor)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Frame ancestor must be a safe HTTP(S) origin")
        ancestor_policy = f"'self' {parsed.scheme}://{parsed.netloc}"

    headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "base-uri 'none'; "
        "form-action 'self'; "
        f"frame-ancestors {ancestor_policy}"
    )
    return headers


SHARED_THEME_CSS = r"""
:root {
  color-scheme: light dark;
  --hb-primary: #03a9f4;
  --hb-primary-hover: #0396d6;
  --hb-primary-soft: rgba(3, 169, 244, .12);
  --hb-bg: #f5f5f5;
  --hb-card: #ffffff;
  --hb-card-alt: #fafafa;
  --hb-divider: #e0e0e0;
  --hb-text: #212121;
  --hb-muted: #727272;
  --hb-success: #43a047;
  --hb-warning: #f9a825;
  --hb-error: #db4437;
  --hb-shadow: 0 2px 6px rgba(0, 0, 0, .12);
  --hb-radius: 12px;
  --bg: var(--hb-bg);
  --panel: var(--hb-card);
  --panel-2: var(--hb-card-alt);
  --line: var(--hb-divider);
  --text: var(--hb-text);
  --muted: var(--hb-muted);
  --accent: var(--hb-primary);
  --accent-strong: var(--hb-primary-hover);
  --danger: var(--hb-error);
  --shadow: var(--hb-shadow);
}
@media (prefers-color-scheme: dark) {
  :root {
    --hb-bg: #111318;
    --hb-card: #1c1f26;
    --hb-card-alt: #252830;
    --hb-divider: #343840;
    --hb-text: #e8eaed;
    --hb-muted: #aeb4bd;
    --hb-primary-soft: rgba(3, 169, 244, .18);
    --hb-shadow: 0 2px 8px rgba(0, 0, 0, .42);
  }
}
* { box-sizing: border-box; }
html { min-height: 100%; background: var(--hb-bg); }
body {
  min-height: 100vh;
  margin: 0;
  color: var(--hb-text);
  background: var(--hb-bg) !important;
  font-family: Roboto, "Noto Sans", system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  line-height: 1.5;
}
body::before { display: none !important; }
main, .shell { position: relative; z-index: 1; }
.hb-nav {
  position: sticky;
  inset: 0 0 auto;
  z-index: 30;
  width: 100%;
  min-height: 64px;
  margin: 0;
  padding: 0 max(16px, calc((100vw - 1180px) / 2));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border: 0;
  border-bottom: 1px solid var(--hb-divider);
  border-radius: 0;
  background: var(--hb-card);
  box-shadow: 0 1px 3px rgba(0, 0, 0, .12);
}
.hb-nav-brand, .hb-nav-link {
  color: var(--hb-text);
  text-decoration: none;
}
.hb-nav-brand {
  min-width: max-content;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1rem;
}
.hb-nav-mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: white;
  background: var(--hb-primary);
  font-size: .88rem;
  font-weight: 800;
  letter-spacing: .02em;
}
.hb-nav-links {
  min-width: 0;
  display: flex;
  align-self: stretch;
  overflow-x: auto;
  scrollbar-width: none;
}
.hb-nav-links::-webkit-scrollbar { display: none; }
.hb-nav-link {
  min-height: 64px;
  padding: 0 15px;
  display: grid;
  place-items: center;
  border-bottom: 3px solid transparent;
  color: var(--hb-muted);
  font-size: .88rem;
  font-weight: 500;
  white-space: nowrap;
  transition: color .15s ease, border-color .15s ease, background .15s ease;
}
.hb-nav-link:hover {
  color: var(--hb-text);
  background: var(--hb-primary-soft);
}
.hb-nav-link.active {
  color: var(--hb-primary);
  border-bottom-color: var(--hb-primary);
  background: transparent;
}
.hb-embedded .hb-nav { display: none; }
.hb-embedded body { min-height: 100%; }
header, .panel, .card {
  border: 1px solid var(--hb-divider) !important;
  background: var(--hb-card) !important;
  color: var(--hb-text);
  box-shadow: var(--hb-shadow);
  backdrop-filter: none !important;
}
header {
  border-radius: var(--hb-radius) !important;
  overflow: visible;
}
header::after { display: none !important; }
h1, h2, h3 {
  color: var(--hb-text);
  letter-spacing: normal;
  font-weight: 500;
}
h1 { font-size: clamp(1.5rem, 3vw, 2rem); }
p, .subtitle, .meta, .friendly, .status { color: var(--hb-muted); }
.panel, .card { border-radius: var(--hb-radius) !important; }
.card {
  transition: border-color .15s ease, box-shadow .15s ease;
}
.card:hover {
  border-color: rgba(3, 169, 244, .55) !important;
  box-shadow: 0 3px 10px rgba(0, 0, 0, .15);
  transform: none;
}
button, .btn, input, select, textarea {
  min-height: 42px;
  border-radius: 8px !important;
  font: inherit;
  transition: border-color .15s ease, background .15s ease, color .15s ease,
    box-shadow .15s ease;
}
input, select, textarea {
  border: 1px solid var(--hb-divider) !important;
  background: var(--hb-card-alt) !important;
  color: var(--hb-text) !important;
}
input::placeholder, textarea::placeholder { color: var(--hb-muted); }
button, .btn {
  border: 1px solid var(--hb-divider) !important;
  background: var(--hb-card-alt);
  color: var(--hb-text);
  font-weight: 500;
  cursor: pointer;
}
button:hover:not(:disabled), .btn:hover:not(:disabled) {
  border-color: var(--hb-primary) !important;
  background: var(--hb-primary-soft);
  transform: none;
}
button.primary, .btn.primary, button:not(.secondary).active {
  border-color: var(--hb-primary) !important;
  background: var(--hb-primary);
  color: white;
  box-shadow: none;
}
button.primary:hover:not(:disabled), .btn.primary:hover:not(:disabled) {
  background: var(--hb-primary-hover);
}
button.danger {
  color: var(--hb-error);
  background: transparent;
}
button:disabled, .btn:disabled { opacity: .5; }
:focus-visible {
  outline: 3px solid rgba(3, 169, 244, .3) !important;
  outline-offset: 2px;
}
.badge {
  border-color: var(--hb-divider) !important;
  background: var(--hb-primary-soft);
  color: var(--hb-primary);
}
.executed, .completed { color: var(--hb-success) !important; }
.rejected, .failed, .error { color: var(--hb-error) !important; }
pre, details {
  border: 1px solid var(--hb-divider);
  border-radius: 8px !important;
  background: var(--hb-card-alt) !important;
}
summary { color: var(--hb-primary) !important; }
::selection { color: white; background: var(--hb-primary); }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb {
  border: 2px solid transparent;
  border-radius: 999px;
  background: rgba(114, 114, 114, .45);
  background-clip: padding-box;
}
.hb-chat .shell { padding-top: 18px; }
.hb-chat .chat { box-shadow: var(--hb-shadow); }
.hb-chat .composer {
  background: var(--hb-card-alt) !important;
  backdrop-filter: none;
}
.hb-chat .message {
  border-color: var(--hb-divider);
  background: var(--hb-card-alt);
  box-shadow: none;
}
.hb-chat .message.user {
  border-color: rgba(3, 169, 244, .35);
  background: var(--hb-primary-soft);
}
.hb-memory main, .hb-audit main { max-width: 1180px; }
.hb-memory header, .hb-audit header, .hb-autonomy header { margin-top: 18px; }
.hb-memory .list {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}
.hb-memory .card {
  min-height: 210px;
  display: flex;
  flex-direction: column;
}
.hb-memory .card .value { flex: 1; font-size: 1rem; line-height: 1.6; }
.hb-memory .card .actions { margin-top: 18px; }
.hb-audit .card { padding: 20px; }
.hb-audit .card h3 { margin-top: 0; font-size: 1.05rem; }
.hb-audit .card > div:not(.meta) { margin-top: 12px; line-height: 1.55; }
.hb-audit pre { max-height: 430px; overflow: auto; }
.hb-autonomy .shell { width: min(1200px, 100%); padding-top: 18px; }
.hb-autonomy .entity {
  border-color: var(--hb-divider);
  background: var(--hb-card-alt);
  box-shadow: none;
  transition: border-color .15s ease, background .15s ease;
}
.hb-autonomy .entity:hover {
  border-color: var(--hb-primary);
  background: var(--hb-card-alt);
  transform: none;
}
.hb-autonomy input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--hb-primary);
}
.hb-autonomy label.toggle {
  min-height: 40px;
  padding: 7px 10px;
  border: 1px solid var(--hb-divider);
  border-radius: 8px;
  background: var(--hb-card);
}
@media (max-width: 760px) {
  .hb-nav { min-height: 58px; padding: 0 8px; gap: 8px; }
  .hb-nav-brand strong { display: none; }
  .hb-nav-mark { width: 38px; height: 38px; }
  .hb-nav-link { min-height: 58px; padding: 0 10px; font-size: .78rem; }
  main, .shell { padding: 12px !important; }
  header { align-items: flex-start !important; }
  .panel, .card { border-radius: 10px !important; }
  input, select, textarea, button, .btn { min-height: 44px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition: none !important;
  }
}
"""

