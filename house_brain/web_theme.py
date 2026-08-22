"""Shared visual language for House Brain's dependency-free web interfaces."""

from house_brain.languages import language_family

_NAVIGATION_LABELS = {
    "ar": ("المحادثة", "الذكريات", "التدقيق", "الاستقلالية", "السجلات"),
    "de": ("Chat", "Erinnerungen", "Audit", "Autonomie", "Protokolle"),
    "en": ("Chat", "Memories", "Audit", "Autonomy", "Logs"),
    "es": ("Chat", "Memorias", "Auditoría", "Autonomía", "Registros"),
    "fr": ("Chat", "Mémoires", "Audit", "Autonomie", "Journaux"),
    "it": ("Chat", "Memorie", "Audit", "Autonomia", "Log"),
    "ja": ("チャット", "メモリ", "監査", "自律性", "ログ"),
    "ko": ("채팅", "메모리", "감사", "자율성", "로그"),
    "pt": ("Chat", "Memórias", "Auditoria", "Autonomia", "Logs"),
    "zh": ("聊天", "记忆", "审计", "自主", "日志"),
}


def shared_navigation(active: str, language: str) -> str:
    """Render the common navigation without client-side HTML construction."""
    labels = _NAVIGATION_LABELS.get(
        language_family(language), _NAVIGATION_LABELS["en"]
    )
    destinations = (
        ("chat", "/chat", "✦", labels[0]),
        ("memories", "/memories", "◫", labels[1]),
        ("audit", "/audit", "≋", labels[2]),
        ("autonomy", "/autonomy", "⌁", labels[3]),
        ("logs", "/logs", "▤", labels[4]),
    )
    links = "".join(
        f'<a href="{href}" class="hb-nav-link'
        f'{" active" if key == active else ""}"'
        f'{" aria-current=\"page\"" if key == active else ""}>'
        f'<span aria-hidden="true">{icon}</span>{label}</a>'
        for key, href, icon, label in destinations
    )
    return (
        '<nav class="hb-nav" aria-label="House Brain">'
        '<a class="hb-nav-brand" href="/chat" aria-label="House Brain">'
        '<span class="hb-nav-mark">HB</span>'
        '<span><strong>House Brain</strong><small>Local intelligence</small></span>'
        f'</a><div class="hb-nav-links">{links}</div></nav>'
    )

SHARED_THEME_CSS = r"""
:root {
  color-scheme: dark;
  --hb-bg: #070b16;
  --hb-surface: rgba(20, 29, 52, .88);
  --hb-surface-raised: rgba(25, 37, 66, .96);
  --hb-surface-deep: #0c1428;
  --hb-border: rgba(133, 165, 226, .22);
  --hb-border-strong: rgba(117, 167, 255, .52);
  --hb-text: #f5f7ff;
  --hb-muted: #aeb9d4;
  --hb-blue: #78aaff;
  --hb-blue-strong: #4f82e5;
  --hb-blue-soft: rgba(90, 139, 231, .17);
  --hb-green: #72d8a5;
  --hb-red: #ff8c98;
  --hb-shadow: 0 22px 65px rgba(0, 0, 0, .32);
  --hb-radius: 18px;
}
html { min-height: 100%; background: var(--hb-bg); }
body {
  min-height: 100vh;
  color: var(--hb-text);
  background:
    radial-gradient(circle at 12% 0%, rgba(75, 126, 224, .22), transparent 34rem),
    radial-gradient(circle at 90% 18%, rgba(68, 104, 190, .12), transparent 30rem),
    linear-gradient(155deg, #070b16 0%, #0b1224 48%, #101a31 100%);
  background-attachment: fixed;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: .22;
  background-image: linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(to bottom, black, transparent 70%);
}
main, .shell { position: relative; z-index: 1; }
.hb-nav {
  position: sticky;
  top: 14px;
  z-index: 20;
  width: min(1120px, calc(100% - 28px));
  min-height: 70px;
  margin: 14px auto 4px;
  padding: 9px 11px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid var(--hb-border);
  border-radius: 20px;
  background: rgba(11, 17, 34, .82);
  box-shadow: 0 18px 55px rgba(0, 0, 0, .34);
  backdrop-filter: blur(22px) saturate(135%);
}
.hb-nav-brand, .hb-nav-link {
  color: var(--hb-text);
  text-decoration: none;
}
.hb-nav-brand { display: flex; align-items: center; gap: 10px; min-width: max-content; }
.hb-nav-brand > span:last-child { display: grid; line-height: 1.1; }
.hb-nav-brand strong { font-size: .95rem; letter-spacing: -.02em; }
.hb-nav-brand small { margin-top: 4px; color: var(--hb-muted); font-size: .67rem; }
.hb-nav-mark {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  color: #06101f;
  background: linear-gradient(145deg, #92bbff, #5487e7);
  box-shadow: inset 0 1px rgba(255,255,255,.5), 0 8px 24px rgba(75,126,224,.32);
  font-weight: 900;
}
.hb-nav-links { display: flex; align-items: center; gap: 5px; }
.hb-nav-link {
  min-height: 44px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 7px;
  border: 1px solid transparent;
  border-radius: 12px;
  color: var(--hb-muted);
  font-size: .84rem;
  font-weight: 680;
  transition: color .16s ease, border-color .16s ease, background .16s ease,
    transform .16s ease;
}
.hb-nav-link span { color: var(--hb-blue); font-size: 1rem; }
.hb-nav-link:hover { color: var(--hb-text); background: rgba(117,167,255,.08); }
.hb-nav-link.active {
  color: white;
  border-color: rgba(117,167,255,.3);
  background: linear-gradient(135deg, rgba(91,139,231,.28), rgba(67,99,171,.14));
  box-shadow: inset 0 1px rgba(255,255,255,.06);
}
header, .panel, .card {
  border-color: var(--hb-border) !important;
  background: var(--hb-surface) !important;
  box-shadow: var(--hb-shadow);
  backdrop-filter: blur(18px);
}
header {
  position: relative;
  overflow: hidden;
  border-radius: var(--hb-radius) !important;
}
header::after {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--hb-blue), transparent);
  opacity: .75;
}
h1, h2, h3 { color: var(--hb-text); letter-spacing: -.025em; }
h1 { font-weight: 780; }
p, .subtitle, .meta, .friendly, .status { color: var(--hb-muted); }
.panel, .card { border-radius: var(--hb-radius) !important; }
.card { transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease; }
.card:hover {
  border-color: var(--hb-border-strong) !important;
  box-shadow: 0 26px 70px rgba(0, 0, 0, .4);
  transform: translateY(-1px);
}
button, .btn, input, select, textarea {
  border-radius: 12px !important;
  transition: border-color .16s ease, background .16s ease, color .16s ease,
    box-shadow .16s ease, transform .16s ease;
}
input, select, textarea {
  border-color: var(--hb-border) !important;
  background: var(--hb-surface-deep) !important;
  color: var(--hb-text) !important;
}
input::placeholder, textarea::placeholder { color: #7785a7; }
button, .btn {
  border-color: var(--hb-border) !important;
  background: #101a31;
  color: var(--hb-text);
  font-weight: 680;
}
button:hover:not(:disabled), .btn:hover:not(:disabled) {
  border-color: var(--hb-border-strong) !important;
  background: #172544;
  transform: translateY(-1px);
}
button.primary, .btn.primary, button:not(.secondary).active {
  border-color: transparent !important;
  background: linear-gradient(135deg, var(--hb-blue), var(--hb-blue-strong));
  color: #071020;
  box-shadow: 0 8px 24px rgba(70, 119, 213, .28);
}
button.danger { color: var(--hb-red); background: rgba(110, 29, 47, .2); }
button:disabled, .btn:disabled { opacity: .52; transform: none; }
:focus-visible {
  outline: 3px solid rgba(120, 170, 255, .38) !important;
  outline-offset: 2px;
}
.badge {
  background: var(--hb-blue-soft);
  border-color: var(--hb-border) !important;
  color: #cfe0ff;
}
.executed, .completed { color: var(--hb-green) !important; }
.rejected, .failed, .error { color: var(--hb-red) !important; }
pre, details {
  border: 1px solid var(--hb-border);
  border-radius: 13px !important;
  background: rgba(7, 12, 25, .58) !important;
}
summary { padding: 4px 2px; color: var(--hb-blue) !important; }
::selection { color: white; background: rgba(71, 123, 210, .75); }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { border: 2px solid transparent; border-radius: 999px;
  background: rgba(120, 170, 255, .3); background-clip: padding-box; }
.hb-chat .shell { padding-top: 12px; }
.hb-chat .chat { box-shadow: 0 30px 90px rgba(0,0,0,.4); }
.hb-chat .composer { background: rgba(8,14,29,.8); backdrop-filter: blur(14px); }
.hb-chat .message { box-shadow: 0 8px 24px rgba(0,0,0,.16); }
.hb-chat .message.user { box-shadow: 0 8px 28px rgba(61,103,187,.2); }
.hb-memory main, .hb-audit main { max-width: 1120px; }
.hb-memory header, .hb-audit header, .hb-autonomy header { margin-top: 16px; }
.hb-memory .list { grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); }
.hb-memory .card { min-height: 220px; display: flex; flex-direction: column; }
.hb-memory .card .value { flex: 1; font-size: 1.02rem; line-height: 1.62; }
.hb-memory .card .actions { margin-top: 18px; }
.hb-audit .card { padding: 22px; }
.hb-audit .card h3 { margin-top: 0; font-size: 1.05rem; }
.hb-audit .card > div:not(.meta) { margin-top: 12px; line-height: 1.58; }
.hb-audit pre { max-height: 430px; overflow: auto; }
.hb-autonomy .shell { width: min(1200px, 100%); padding-top: 16px; }
.hb-autonomy .entity {
  background: rgba(10,17,34,.52);
  box-shadow: inset 0 1px rgba(255,255,255,.025);
  transition: border-color .16s ease, background .16s ease, transform .16s ease;
}
.hb-autonomy .entity:hover {
  border-color: var(--hb-border-strong);
  background: rgba(18,29,54,.72);
  transform: translateY(-1px);
}
.hb-autonomy input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--hb-blue);
}
.hb-autonomy label.toggle {
  min-height: 38px;
  padding: 7px 9px;
  display: inline-flex;
  align-items: center;
  border: 1px solid rgba(133,165,226,.12);
  border-radius: 10px;
  background: rgba(8,14,28,.38);
}
@media (max-width: 680px) {
  .hb-nav { top: 6px; width: calc(100% - 12px); margin-top: 6px; padding: 7px; }
  .hb-nav-brand > span:last-child { display: none; }
  .hb-nav-links { flex: 1; justify-content: space-around; }
  .hb-nav-link { min-width: 0; padding: 8px; flex-direction: column; gap: 2px;
    font-size: .65rem; }
  .hb-nav-link span { line-height: 1; }
  main, .shell { padding: 12px !important; }
  header { align-items: flex-start !important; }
  .panel, .card { border-radius: 15px !important; }
  input, select, textarea, button, .btn { min-height: 44px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition: none !important;
  }
}
"""
