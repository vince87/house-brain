"""Shared visual language for House Brain's dependency-free web interfaces."""

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
@media (max-width: 680px) {
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
