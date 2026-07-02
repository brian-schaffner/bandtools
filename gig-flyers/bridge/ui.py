"""Shared navigation and mobile-first CSS for bridge HTML pages."""

from __future__ import annotations

import html
from typing import Optional

def band_tools_logo_svg(*, size: int = 36) -> str:
    """Inline SVG matching setlist-helper BandToolsLogo (sm)."""
    return f"""<svg class="site-logo-icon" width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="url(#bt-gradient)"/>
      <path d="M18 42V22l14 10 14-10v20" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="32" cy="32" r="4" fill="white" fill-opacity="0.9"/>
      <path d="M44 18h6v6M44 18l8 8" stroke="#FCD34D" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      <defs>
        <linearGradient id="bt-gradient" x1="8" y1="8" x2="56" y2="56" gradientUnits="userSpaceOnUse">
          <stop stop-color="#6366F1"/>
          <stop offset="1" stop-color="#D97706"/>
        </linearGradient>
      </defs>
    </svg>"""


def base_css() -> str:
    """Band Tools light theme, touch targets, safe-area, and responsive layout."""
    return """
    :root {
      --bg: #4CBB17;
      --surface: #ffffff;
      --surface-2: #f5f5f5;
      --border: #2d7a0e;
      --text: #0a0a0a;
      --muted: #1a4d0a;
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --green: #16a34a;
      --purple: #7c3aed;
      --warn-bg: #fef9c3;
      --warn-text: #a16207;
      --pass-bg: #dcfce7;
      --pass-text: #15803d;
      --tap-min: 44px;
      --page-pad: max(1rem, env(safe-area-inset-left));
      --page-pad-r: max(1rem, env(safe-area-inset-right));
      --page-pad-top: max(0rem, env(safe-area-inset-top));
      --page-pad-bottom: max(1.25rem, env(safe-area-inset-bottom));
      --container-max: 1100px;
    }
    *, *::before, *::after { box-sizing: border-box; }
    html {
      -webkit-text-size-adjust: 100%;
      overflow-x: hidden;
    }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 16px;
      line-height: 1.5;
      color: var(--text);
      background: var(--bg);
      margin: 0;
      padding: 0;
      overflow-x: hidden;
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    h1 { font-size: 1.5rem; margin: 0 0 0.35rem; line-height: 1.25; font-weight: 700; letter-spacing: -0.02em; }
    h2 { font-size: 1.15rem; margin: 0 0 0.75rem; font-weight: 600; }
    h3 { font-size: 1rem; margin: 0 0 0.5rem; font-weight: 600; }
    p { margin: 0 0 0.75rem; }
    .lead, .meta { color: var(--muted); margin-bottom: 1.25rem; }
    .muted { color: var(--muted); font-size: 0.9rem; }
    .page-shell {
      min-height: 100vh;
      min-height: 100dvh;
      background: linear-gradient(
        180deg,
        rgba(76, 187, 23, 0.9) 0%,
        var(--bg) 40%,
        rgba(60, 150, 18, 0.95) 100%
      );
    }
    .page-main {
      max-width: var(--container-max);
      margin: 0 auto;
      padding: 2rem var(--page-pad-r) var(--page-pad-bottom) var(--page-pad);
      width: 100%;
    }
    .site-header {
      border-bottom: 1px solid rgba(45, 122, 14, 0.6);
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      padding: 0.85rem var(--page-pad-r) 0.85rem var(--page-pad);
      padding-top: max(0.85rem, env(safe-area-inset-top));
    }
    .site-header-inner {
      max-width: var(--container-max);
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.75rem 1rem;
    }
    .site-header-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      gap: 0.75rem;
    }
    .site-brand {
      font-weight: 700;
      color: var(--text);
      text-decoration: none;
      min-height: var(--tap-min);
      display: inline-flex;
      align-items: center;
      gap: 0.65rem;
      letter-spacing: -0.02em;
      transition: opacity 0.15s;
    }
    .site-brand:hover { text-decoration: none; opacity: 0.9; }
    .site-logo-icon { flex-shrink: 0; display: block; }
    .site-wordmark { display: flex; flex-direction: column; gap: 0.05rem; }
    .site-wordmark-title { font-size: 1.125rem; line-height: 1.2; }
    .site-wordmark-tagline { font-size: 0.75rem; font-weight: 400; color: var(--muted); }
    .site-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
      align-items: center;
      width: 100%;
    }
    .site-nav a, .site-nav .nav-active, .site-nav .nav-divider {
      display: inline-flex;
      align-items: center;
      min-height: var(--tap-min);
      padding: 0 0.85rem;
      border-radius: 8px;
      font-size: 0.95rem;
      color: var(--muted);
      text-decoration: none;
      border: 1px solid transparent;
    }
    .site-nav .nav-divider {
      padding: 0;
      min-height: 1.5rem;
      width: 1px;
      background: var(--border);
      margin: 0 0.15rem;
      border-radius: 0;
      flex-shrink: 0;
    }
    .site-nav a:hover {
      color: var(--text);
      background: var(--surface-2);
      text-decoration: none;
    }
    .site-nav .nav-active {
      color: var(--text);
      background: var(--surface-2);
      border-color: var(--border);
      font-weight: 600;
    }
    .all-tools-link {
      display: inline-flex;
      align-items: center;
      min-height: var(--tap-min);
      padding: 0 0.5rem;
      color: var(--muted);
      font-size: 0.875rem;
      font-weight: 500;
      text-decoration: none;
      white-space: nowrap;
      transition: color 0.15s;
    }
    .all-tools-link:hover { color: var(--text); text-decoration: none; }
    .back-link {
      display: inline-flex;
      align-items: center;
      min-height: var(--tap-min);
      padding: 0 0.5rem;
      color: var(--muted);
      font-size: 0.875rem;
      font-weight: 500;
    }
    .back-link:hover { color: var(--text); text-decoration: none; }
    .panel, .card-panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.1rem;
      margin-bottom: 1rem;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }
    .btn, button, .button, input[type="submit"] {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: var(--tap-min);
      padding: 0.55rem 1.1rem;
      font-size: 1rem;
      font-family: inherit;
      line-height: 1.2;
      border: none;
      border-radius: 8px;
      cursor: pointer;
      text-decoration: none;
      background: var(--accent);
      color: #fff;
      font-weight: 500;
      -webkit-tap-highlight-color: transparent;
      transition: filter 0.15s;
    }
    .btn:hover, button:hover, .button:hover { filter: brightness(1.05); text-decoration: none; }
    .btn-secondary, .button.secondary { background: #4f46e5; }
    .btn-green { background: var(--green); }
    .btn-purple, button.regenerate, .regenerate-btn { background: var(--purple); }
    .btn-block { width: 100%; }
    .btn-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
    }
    .btn-row form { margin: 0; }
    .badge {
      display: inline-block;
      font-size: 0.8rem;
      background: var(--surface-2);
      border: 1px solid var(--border);
      padding: 0.2rem 0.55rem;
      border-radius: 999px;
      color: var(--muted);
    }
    .badge-approved { background: var(--pass-bg); border-color: var(--green); color: var(--pass-text); }
    .badge-pending { background: var(--warn-bg); border-color: #9e6a03; color: var(--warn-text); }
    code {
      background: var(--surface-2);
      padding: 0.15rem 0.4rem;
      border-radius: 4px;
      font-size: 0.9em;
    }
    img { max-width: 100%; height: auto; display: block; }
    textarea, input[type="text"] {
      width: 100%;
      font-size: 16px;
      font-family: inherit;
      padding: 0.65rem 0.75rem;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--bg);
      color: var(--text);
      margin: 0.5rem 0;
    }
    textarea { min-height: 4.5rem; resize: vertical; }
    .sticky-actions {
      position: sticky;
      bottom: 0;
      z-index: 20;
      margin: 1rem calc(-1 * var(--page-pad)) calc(-1 * var(--page-pad-bottom));
      padding: 0.75rem var(--page-pad) max(0.75rem, env(safe-area-inset-bottom)) var(--page-pad-r);
      background: linear-gradient(transparent, rgba(76, 187, 23, 0.95) 12%, var(--bg));
      border-top: 1px solid var(--border);
    }
    .collapsible-section {
      border: 1px solid var(--border);
      border-radius: 10px;
      margin-bottom: 1rem;
      background: var(--surface);
      overflow: hidden;
    }
    .collapsible-section > summary {
      cursor: pointer;
      padding: 0.85rem 1rem;
      font-weight: 600;
      list-style: none;
      min-height: var(--tap-min);
      display: flex;
      align-items: center;
    }
    .collapsible-section > summary::-webkit-details-marker { display: none; }
    .collapsible-section > summary::after {
      content: "▸";
      margin-left: auto;
      color: var(--muted);
      transition: transform 0.15s;
    }
    .collapsible-section[open] > summary::after { transform: rotate(90deg); }
    .collapsible-section > .collapsible-body { padding: 0 1rem 1rem; }
    @media (max-width: 640px) {
      .page-main { padding-top: 1.25rem; }
      h1 { font-size: 1.35rem; }
      .site-header-top { flex-wrap: wrap; }
      .site-nav { gap: 0.25rem; }
      .site-nav a, .site-nav .nav-active {
        flex: 1 1 auto;
        justify-content: center;
        padding: 0 0.5rem;
        font-size: 0.875rem;
      }
      .site-nav .nav-divider { display: none; }
    }
    """


def home_css() -> str:
    return """
    .mode-cards { display: grid; gap: 1rem; }
    @media (min-width: 640px) { .mode-cards { grid-template-columns: 1fr; } }
    .mode-card {
      background: var(--surface);
      border: 1px solid rgba(229, 229, 229, 0.8);
      border-radius: 12px;
      padding: 1.25rem;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
      position: relative;
      overflow: hidden;
    }
    .mode-card::before {
      content: "";
      position: absolute;
      inset: 0 auto auto 0;
      width: 100%;
      height: 4px;
      background: linear-gradient(90deg, #2d7a0e, #4CBB17);
    }
    .mode-card h2 { margin-top: 0; }
    .mode-card .btn { margin-top: 0.5rem; }
    .mode-card-featured { border-color: rgba(45, 122, 14, 0.5); }
    .mode-card-featured::before {
      background: linear-gradient(90deg, #3c9612, #6dd82e);
    }
    """


def picker_css() -> str:
    return """
    .gig-cards { display: grid; gap: 0.85rem; }
    .gig-card {
      background: var(--surface);
      border: 1px solid rgba(229, 229, 229, 0.8);
      border-radius: 12px;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }
    .gig-card-head { display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: flex-start; }
    .gig-card-date {
      font-weight: 700;
      font-size: 1.05rem;
      min-width: 4.5rem;
    }
    .gig-card-venue { flex: 1; min-width: 0; }
    .gig-card-venue strong { display: block; font-size: 1.05rem; }
    .gig-card-meta { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }
    .gig-card-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .gig-card-actions form { flex: 1; min-width: 140px; }
    .gig-card-actions .btn, .gig-card-actions button { width: 100%; }
    .cache-note { margin-top: 1.5rem; }
    .picker-table { display: none; }
    @media (min-width: 900px) {
      .gig-cards { display: none; }
      .picker-table { display: table; width: 100%; border-collapse: collapse; }
      .picker-table th, .picker-table td {
        border-bottom: 1px solid var(--border);
        padding: 0.75rem 0.5rem;
        text-align: left;
        vertical-align: top;
      }
      .picker-table th { color: var(--muted); font-size: 0.85rem; }
    }
    """


def review_css() -> str:
    return """
    .page-header { margin-bottom: 1.25rem; }
    .current-round { margin-bottom: 1.5rem; }
    .options-grid, .history-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: 1fr;
    }
    @media (min-width: 640px) {
      .options-grid { grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
      .history-grid { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
    }
    .review-option-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
    }
    .review-option-card img {
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .review-option-card .approve-form button { width: 100%; background: var(--green); }
    .review-option-card .revise-form button { width: 100%; }
    .approved-banner {
      background: var(--pass-bg);
      border: 1px solid var(--green);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 1rem;
    }
    .approved-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-start; }
    .approved-thumb { margin: 0; max-width: 220px; flex-shrink: 0; }
    .approved-thumb img, .history-approved-thumb {
      width: 100%;
      max-width: 180px;
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .prior-approvals ul { list-style: none; padding: 0; margin: 0; }
    .prior-approval { margin-bottom: 0.75rem; }
    .research-panel {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 1rem;
      background: var(--surface);
    }
    .research-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: 1fr;
    }
    @media (min-width: 640px) {
      .research-grid { grid-template-columns: 1fr minmax(160px, 240px); }
    }
    .research-photo figcaption { font-size: 0.85rem; color: var(--muted); margin-top: 0.35rem; }
    .regenerate-bar {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 1rem;
      background: var(--surface);
    }
    .regenerate-bar .regenerate-btn { width: 100%; }
    @media (min-width: 640px) {
      .regenerate-bar .regenerate-btn { width: auto; }
    }
    .reviewer-note {
      font-size: 0.9rem;
      margin: 0;
      padding: 0.45rem 0.6rem;
      border-radius: 6px;
    }
    .reviewer-note.pass { background: var(--pass-bg); color: var(--pass-text); }
    .reviewer-note.warn { background: var(--warn-bg); color: var(--warn-text); }
    .history-grid figure {
      margin: 0;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.5rem;
      background: var(--surface-2);
    }
    .history-grid figcaption { font-size: 0.85rem; color: var(--muted); margin-bottom: 0.35rem; }
    .feedback-list { list-style: none; padding: 0; margin: 0; }
    .feedback-list li { padding: 0.5rem 0; border-bottom: 1px solid var(--border); }
    details.history-round {
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-bottom: 0.75rem;
      background: rgba(76, 187, 23, 0.3);
    }
    details.history-round > summary {
      padding: 0.65rem 0.85rem;
      cursor: pointer;
      font-weight: 600;
      min-height: var(--tap-min);
      display: flex;
      align-items: center;
      list-style: none;
    }
    details.history-round > summary::-webkit-details-marker { display: none; }
    details.history-round .history-grid { padding: 0 0.85rem 0.85rem; }
    .option-actions { display: flex; flex-direction: column; gap: 0.75rem; }
  """


def progress_css() -> str:
    return """
    :root {
      --blue-top: #818cf8;
      --blue-bottom: #6366f1;
      --vessel-border: #2d7a0e;
      --bg-empty: #e8f5e0;
    }
    .progress-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.1rem;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }
    .gig-line { margin: 0 0 1rem; }
    .overall-status { font-size: 0.95rem; font-weight: 600; margin: 0.5rem 0 1rem; min-height: 1.4em; }
    .overall-detail { font-size: 0.9rem; color: var(--muted); margin: -0.5rem 0 1rem; }
    .provider-badge {
      font-size: 0.85rem;
      color: #1a4d0a;
      background: #d4f0c8;
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      margin: 0 0 0.75rem;
    }
    .options-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 1rem;
      margin: 1rem 0;
    }
    @media (min-width: 720px) {
      .options-grid { grid-template-columns: repeat(3, 1fr); }
    }
    .option-card {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.85rem;
      background: var(--surface-2);
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .option-card.active { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(99,102,241,0.2); }
    .option-card.passed { border-color: var(--green); }
    .option-card.failed { border-color: #ef4444; }
    .option-header { display: flex; align-items: center; gap: 0.5rem; }
    .option-letter {
      font-size: 1.1rem;
      font-weight: 700;
      width: 2.25rem;
      height: 2.25rem;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      background: var(--bg);
    }
    .option-card.passed .option-letter { background: var(--pass-bg); color: var(--green); }
    .option-card.failed .option-letter { background: #fef2f2; color: #ef4444; }
    .engine-badge {
      font-size: 0.75rem;
      color: var(--muted);
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.15rem 0.4rem;
      margin-left: auto;
    }
    .attempt-badge {
      font-size: 0.7rem;
      text-transform: uppercase;
      color: var(--muted);
      background: var(--bg);
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
    }
    .phase-label { font-size: 0.8rem; font-weight: 600; color: var(--muted); text-transform: capitalize; }
    .option-card.passed .phase-label { color: var(--green); }
    .option-card.failed .phase-label { color: #ef4444; }
    .option-preview {
      position: relative;
      height: min(52vw, 280px);
      min-height: 180px;
      border-radius: 10px;
      overflow: hidden;
      background: var(--bg-empty);
      border: 3px solid var(--vessel-border);
    }
    @media (min-width: 720px) { .option-preview { height: 200px; min-height: 200px; } }
    .option-card.outline-review .option-preview { border-color: var(--green); }
    .option-card.outline-pass .option-preview { border-color: var(--accent); }
    .option-card.outline-fail .option-preview { border-color: #ef4444; }
    .option-card.fail-flash .option-preview { animation: failFlash 0.75s ease-out; }
    .option-thumb { width: 100%; height: 100%; object-fit: cover; display: none; }
    .option-preview.show-image .option-thumb { display: block; }
    .option-preview.show-image .vessel-layer { display: none; }
    .vessel-layer { position: absolute; inset: 0; }
    .vessel { position: relative; height: 100%; overflow: hidden; background: var(--bg-empty); }
    .vessel-fill {
      position: absolute; left: 0; right: 0; bottom: 0; height: 0%;
      background: linear-gradient(180deg, var(--blue-top) 0%, var(--blue-bottom) 100%);
    }
    .vessel-fill.filling { transition: none; }
    .vessel-fill.locked-full { height: 100% !important; animation: none; transition: height 0.2s ease-out; }
    .vessel-fill::before {
      content: ""; position: absolute; left: -50%; top: -8px; width: 200%; height: 16px;
      background: rgba(255,255,255,0.15); border-radius: 45%;
      animation: wave 2.8s ease-in-out infinite;
    }
    .vessel-fill.locked-full::before { display: none; }
    .fill-pct {
      position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
      font-size: 1.25rem; font-weight: 700; color: var(--muted); z-index: 2; pointer-events: none;
    }
    .option-card.generating .fill-pct, .option-card.remaking .fill-pct {
      color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.25);
    }
    .option-note { font-size: 0.8rem; color: #ef4444; line-height: 1.35; min-height: 2.5em; }
    .option-card.passed .option-note { color: var(--green); }
    @keyframes wave {
      0%, 100% { transform: translateX(0) rotate(0deg); }
      50% { transform: translateX(12%) rotate(2deg); }
    }
    @keyframes failFlash {
      0%, 100% { border-color: #ef4444; }
      50% { border-color: #f87171; box-shadow: inset 0 0 18px 4px rgba(239, 68, 68, 0.2); }
    }
    .log-panel {
      background: #e8f5e0;
      color: var(--muted);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.55rem 0.7rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.75rem;
      max-height: 88px;
      overflow-y: auto;
      margin: 0.75rem 0 0.5rem;
    }
    .log-line { margin: 0.1rem 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .error { color: #ef4444; }
    """


def site_nav(*, active: str = "", back_href: Optional[str] = None, back_label: str = "Back") -> str:
    """Band Tools header with cross-tool nav and Gig Flyers sub-nav."""
    from bridge.review import (
        band_tools_home_path,
        home_page_path,
        pick_page_path,
        route_path,
        setlist_loader_path,
    )

    tools_home = html.escape(band_tools_home_path())
    setlist = html.escape(setlist_loader_path())
    flyers_home = html.escape(home_page_path())
    pick = html.escape(pick_page_path())
    shell_studio = html.escape(route_path("/shell"))
    logo = band_tools_logo_svg(size=36)

    flyers_tool_cls = "nav-active" if active in ("home", "pick", "review", "progress", "shell") else ""
    home_cls = "nav-active" if active == "home" else ""
    pick_cls = "nav-active" if active == "pick" else ""
    review_cls = "nav-active" if active == "review" else ""
    progress_cls = "nav-active" if active == "progress" else ""
    shell_cls = "nav-active" if active == "shell" else ""

    review_item = (
        f'<span class="{review_cls} nav-active">Review</span>' if active == "review" else ""
    )
    progress_item = (
        f'<span class="{progress_cls} nav-active">Status</span>' if active == "progress" else ""
    )

    back_html = ""
    if back_href:
        back_html = (
            f'<a class="back-link" href="{html.escape(back_href)}">'
            f"← {html.escape(back_label)}</a>"
        )
    elif active in ("pick", "review", "progress"):
        back_html = f'<a class="all-tools-link" href="{tools_home}">← All tools</a>'

    return f"""
  <header class="site-header">
    <div class="site-header-inner">
      <div class="site-header-top">
        <a class="site-brand" href="{tools_home}">
          {logo}
          <span class="site-wordmark">
            <span class="site-wordmark-title">Band Tools</span>
            <span class="site-wordmark-tagline">For gigging musicians</span>
          </span>
        </a>
        {back_html}
      </div>
      <nav class="site-nav" aria-label="Main">
        <a href="{tools_home}">All tools</a>
        <a href="{setlist}">Setlist Loader</a>
        <span class="{flyers_tool_cls} nav-active">Gig Flyers</span>
        <span class="nav-divider" aria-hidden="true"></span>
        <a class="{home_cls}" href="{flyers_home}">Home</a>
        <a class="{pick_cls}" href="{pick}">Pick gig</a>
        <a class="{shell_cls}" href="{shell_studio}">Shell studio</a>
        {review_item}
        {progress_item}
      </nav>
    </div>
  </header>"""


def page_head(title: str, *, extra_css: str = "") -> str:
    title_esc = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{title_esc}</title>
  <style>
{base_css()}
{extra_css}
  </style>
</head>
<body>
<div class="page-shell">
"""


def page_close() -> str:
    return "</div>\n</body>\n</html>"
