"""Flyer Agent HTML UI — three-panel workspace layout."""

from __future__ import annotations

import html
import json
from typing import Any, Optional

from bridge.review import review_page_path, route_path
from bridge.ui import base_css, page_close, page_head, site_nav
from flyer_agent.urls import flyer_asset_url


def agent_css() -> str:
    return base_css() + """
    :root {
      --agent-sidebar-w: 280px;
      --agent-header-h: auto;
      --agent-chat-min: 220px;
      --agent-chat-max: 320px;
      --agent-poster-w: 200px;
      --agent-ink: #0f172a;
      --agent-panel: #ffffff;
      --agent-panel-border: rgba(15, 23, 42, 0.08);
      --agent-accent: #4f46e5;
      --agent-accent-soft: #eef2ff;
    }
    .page-main.agent-workspace-wrap {
      max-width: none;
      padding: 0.75rem var(--page-pad) var(--page-pad-bottom);
      margin: 0;
    }
    .agent-workspace {
      display: grid;
      grid-template-columns: var(--agent-sidebar-w) minmax(0, 1fr);
      gap: 0.75rem;
      min-height: calc(100dvh - 9rem);
      align-items: stretch;
    }
    .agent-sidebar {
      background: var(--agent-panel);
      border: 1px solid var(--agent-panel-border);
      border-radius: 14px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
    }
    .agent-sidebar-head {
      padding: 0.85rem 1rem;
      border-bottom: 1px solid var(--agent-panel-border);
      background: linear-gradient(180deg, #f8fafc 0%, #fff 100%);
    }
    .agent-sidebar-head h2 { margin: 0; font-size: 0.95rem; }
    .agent-sidebar-head .muted { margin: 0.15rem 0 0; font-size: 0.78rem; }
    .agent-gig-nav {
      list-style: none;
      margin: 0;
      padding: 0.35rem;
      overflow-y: auto;
      flex: 1;
    }
    .agent-gig-nav li { margin: 0; }
    .agent-gig-nav a {
      display: block;
      padding: 0.65rem 0.75rem;
      border-radius: 10px;
      color: var(--agent-ink);
      text-decoration: none;
      border: 1px solid transparent;
    }
    .agent-gig-nav a:hover { background: #f8fafc; text-decoration: none; }
    .agent-gig-nav a.active {
      background: var(--agent-accent-soft);
      border-color: rgba(79, 70, 229, 0.18);
      color: #312e81;
    }
    .agent-gig-nav .gig-line-1 { font-weight: 600; font-size: 0.92rem; }
    .agent-gig-nav .gig-line-2 {
      font-size: 0.76rem;
      color: #64748b;
      margin-top: 0.15rem;
      display: flex;
      gap: 0.35rem;
      flex-wrap: wrap;
      align-items: center;
    }
    .agent-main {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) minmax(var(--agent-chat-min), var(--agent-chat-max));
      gap: 0.75rem;
      min-width: 0;
    }
    .agent-gig-meta {
      background: var(--agent-panel);
      border: 1px solid var(--agent-panel-border);
      border-radius: 14px;
      padding: 1rem 1.1rem;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }
    .agent-gig-meta-top {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .agent-gig-meta h1 {
      margin: 0;
      font-size: 1.35rem;
      color: var(--agent-ink);
    }
    .agent-gig-meta .meta-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 0.65rem 1rem;
      margin-top: 0.85rem;
      font-size: 0.86rem;
    }
    .agent-gig-meta .meta-item label {
      display: block;
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #64748b;
      margin-bottom: 0.15rem;
    }
    .agent-gig-meta .meta-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
    }
    .agent-posters-panel {
      background: var(--agent-panel);
      border: 1px solid var(--agent-panel-border);
      border-radius: 14px;
      padding: 1rem;
      overflow: auto;
      min-height: 0;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }
    .agent-posters-panel h2 {
      margin: 0 0 0.75rem;
      font-size: 0.95rem;
      color: #334155;
    }
    .agent-flyer-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, var(--agent-poster-w)));
      gap: 0.65rem;
      justify-content: start;
      align-items: start;
    }
    .agent-flyer-card {
      border: 1px solid var(--agent-panel-border);
      border-radius: 10px;
      overflow: hidden;
      background: #f8fafc;
      max-width: var(--agent-poster-w);
    }
    .agent-flyer-card.selected {
      border-color: var(--agent-accent);
      box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15);
    }
    .agent-flyer-card img {
      width: 100%;
      display: block;
      aspect-ratio: 2/3;
      object-fit: cover;
      background: #e2e8f0;
    }
    .agent-flyer-card .flyer-cap {
      padding: 0.45rem 0.55rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.78rem;
    }
    .agent-flyer-card .flyer-cap .btn-secondary {
      font-size: 0.72rem;
      padding: 0.25rem 0.45rem;
    }
    .agent-flyer-card .flyer-cap .btn-approve {
      font-size: 0.72rem;
      padding: 0.25rem 0.45rem;
      background: var(--green, #16a34a);
      color: #fff;
      border: none;
      border-radius: 6px;
      cursor: pointer;
    }
    .agent-wild-badge {
      display: block;
      font-size: 0.65rem;
      font-weight: 600;
      color: #9a3412;
      background: #ffedd5;
      border-radius: 4px;
      padding: 0.12rem 0.35rem;
      margin-top: 0.2rem;
      line-height: 1.3;
    }
    .agent-empty-state {
      color: #64748b;
      padding: 2rem 1rem;
      text-align: center;
    }
    .agent-chat-panel {
      background: var(--agent-panel);
      border: 1px solid var(--agent-panel-border);
      border-radius: 14px;
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }
    .agent-chat-head {
      padding: 0.65rem 1rem;
      border-bottom: 1px solid var(--agent-panel-border);
      font-size: 0.86rem;
      font-weight: 600;
      color: #334155;
      background: #f8fafc;
    }
    .agent-chat-log {
      flex: 1;
      overflow-y: auto;
      padding: 0.85rem 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
      min-height: 120px;
    }
    .agent-chat-msg {
      max-width: 92%;
      padding: 0.65rem 0.8rem;
      border-radius: 12px;
      font-size: 0.88rem;
      line-height: 1.45;
      white-space: pre-wrap;
    }
    .agent-chat-msg.user {
      align-self: flex-end;
      background: var(--agent-accent);
      color: #fff;
      border-bottom-right-radius: 4px;
    }
    .agent-chat-msg.agent {
      align-self: flex-start;
      background: #f1f5f9;
      color: #0f172a;
      border-bottom-left-radius: 4px;
    }
    .agent-chat-compose {
      border-top: 1px solid var(--agent-panel-border);
      padding: 0.75rem;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 0.5rem;
      align-items: end;
      background: #fff;
    }
    .agent-chat-compose textarea {
      width: 100%;
      min-height: 44px;
      max-height: 120px;
      resize: vertical;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 0.6rem 0.75rem;
      font: inherit;
    }
    .agent-chat-compose button {
      min-height: 44px;
      white-space: nowrap;
    }
    .source-badge {
      display: inline-block;
      font-size: 0.68rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 0.12rem 0.4rem;
      border-radius: 999px;
    }
    .source-background { background: #dbeafe; color: #1d4ed8; }
    .source-interactive { background: #fef3c7; color: #b45309; }
    .source-agent { background: #ede9fe; color: #6d28d9; }
    .source-none { background: #f1f5f9; color: #64748b; }
    .login-panel {
      max-width: 420px;
      margin: 2rem auto;
      background: var(--surface);
      border-radius: 16px;
      padding: 2rem;
      text-align: center;
      box-shadow: 0 8px 32px rgba(0,0,0,0.12);
    }
    .login-panel .btn { width: 100%; margin-top: 1rem; }
    .catalog-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 0.75rem;
    }
    .catalog-item {
      background: var(--surface-2);
      border-radius: 8px;
      padding: 0.75rem;
      font-size: 0.9rem;
    }
    @media (max-width: 900px) {
      .agent-workspace {
        grid-template-columns: 1fr;
        min-height: auto;
      }
      .agent-sidebar { max-height: 220px; }
      .agent-main {
        grid-template-rows: auto minmax(280px, 1fr) minmax(240px, 300px);
      }
    }
    """


def _source_badge(source_key: str, label: str) -> str:
    cls = f"source-badge source-{html.escape(source_key)}"
    return f'<span class="{cls}">{html.escape(label)}</span>'


def _sidebar_nav(board: dict[str, Any], selected_gig_id: Optional[str]) -> str:
    items: list[str] = []
    for gig in board.get("gigs", []):
        gid = gig["gig_id"]
        active = "active" if gid == selected_gig_id else ""
        href = html.escape(route_path(f"/agent/gig/{gid}"))
        venue = html.escape(gig["venue"])
        short_date = html.escape(gig["short_date"])
        badge = _source_badge(gig.get("generation_source", "none"), gig.get("generation_source_label", ""))
        workflow = html.escape(gig.get("workflow_label", ""))
        items.append(
            f"""
            <li>
              <a class="{active}" href="{href}">
                <div class="gig-line-1">{short_date} · {venue}</div>
                <div class="gig-line-2">{badge}<span>{workflow}</span></div>
              </a>
            </li>
            """
        )
    if not items:
        return '<ul class="agent-gig-nav"><li class="agent-empty-state">No upcoming gigs</li></ul>'
    return f'<ul class="agent-gig-nav">{"".join(items)}</ul>'


def _meta_panel(
    detail: Optional[dict[str, Any]],
    recommendation: dict[str, Any],
) -> str:
    if not detail:
        return """
        <section class="agent-gig-meta">
          <div class="agent-empty-state">
            <h1>Select a gig</h1>
            <p class="muted">Choose an upcoming show from the left to view details and posters.</p>
          </div>
        </section>
        """

    event = detail.get("event") or {}
    venue = html.escape(event.get("venue") or detail.get("gig_id", ""))
    short_date = html.escape(event.get("short_date") or event.get("date") or "")
    time_label = html.escape(event.get("time") or "TBA")
    title = html.escape(event.get("title") or "")
    gig_id = html.escape(detail["gig_id"])
    source_badge = _source_badge(detail.get("generation_source", "none"), detail.get("generation_source_label", ""))
    workflow = html.escape(detail.get("workflow_label", ""))
    round_num = detail.get("round") or 0
    research = detail.get("research") or {}
    venue_type = html.escape(str(research.get("venue_type") or "—"))
    design_lang = html.escape(str(research.get("design_language") or "—"))
    photo = detail.get("selected_photo") or {}
    photo_label = html.escape(str(photo.get("id") or photo.get("type") or "—"))

    actions: list[str] = []
    if detail.get("can_generate"):
        actions.append(
            f'<form method="post" action="{html.escape(route_path(f"/agent/gig/{detail["gig_id"]}/generate"))}">'
            f'<button type="submit">Generate 3 options</button></form>'
        )
    if detail.get("can_regenerate"):
        actions.append(
            f'<form method="post" action="{html.escape(route_path(f"/agent/gig/{detail["gig_id"]}/regenerate"))}"'
            f' onsubmit="return confirm(\'Regenerate fresh options?\');">'
            f'<button type="submit" class="btn-purple">Regenerate</button></form>'
        )
    if detail.get("flyers"):
        review = html.escape(review_page_path(detail["gig_id"]))
        actions.append(f'<a class="btn btn-secondary" href="{review}">Full review</a>')

    actions_html = "".join(actions) or '<span class="muted">No actions yet</span>'

    return f"""
    <section class="agent-gig-meta">
      <div class="agent-gig-meta-top">
        <div>
          <h1>{short_date} @ {venue}</h1>
          <p class="muted" style="margin:0.25rem 0 0">{title}</p>
        </div>
        <div class="meta-actions">{actions_html}</div>
      </div>
      <div class="meta-grid">
        <div class="meta-item"><label>When</label>{time_label}</div>
        <div class="meta-item"><label>Status</label>{source_badge} {workflow}</div>
        <div class="meta-item"><label>Round</label><span id="agent-gig-round">{round_num}</span></div>
        <div class="meta-item"><label>Venue type</label>{venue_type}</div>
        <div class="meta-item"><label>Design language</label>{design_lang}</div>
        <div class="meta-item"><label>Band photo</label>{photo_label}</div>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.84rem">{html.escape(recommendation.get("message", ""))}</p>
      <input type="hidden" id="agent-gig-id" value="{gig_id}" />
    </section>
    """


def _posters_panel(detail: Optional[dict[str, Any]]) -> str:
    if not detail:
        return """
        <section class="agent-posters-panel">
          <h2>Posters</h2>
          <div class="agent-empty-state">Posters for the selected gig will appear here.</div>
        </section>
        """
    flyers = detail.get("flyers") or []
    if not flyers:
        return """
        <section class="agent-posters-panel">
          <h2>Posters</h2>
          <div class="agent-empty-state">No posters yet — ask the agent to generate options, or use Generate above.</div>
        </section>
        """

    cards: list[str] = []
    round_num = int(detail.get("round") or 0)
    updated_at = str(detail.get("updated_at") or "")
    can_approve = bool(flyers) and detail.get("workflow") != "approved"
    for flyer in flyers:
        opt = html.escape(flyer["option"])
        img_url = html.escape(
            flyer_asset_url(flyer["path"], round_num=round_num, updated_at=updated_at)
        )
        approve_btn = (
            f'<button type="button" class="btn-approve agent-approve-option" data-option="{opt}">Approve</button>'
            if can_approve
            else ""
        )
        wild_badge = (
            '<span class="agent-wild-badge">Fully designed · experimental<br><span style="font-weight:400">Faces may not match</span></span>'
            if flyer.get("is_wild")
            else ""
        )
        cards.append(
            f"""
            <article class="agent-flyer-card" data-option="{opt}">
              <img src="{img_url}" alt="Option {opt}" loading="lazy" />
              <div class="flyer-cap">
                <div>
                  <strong>Option {opt}</strong>
                  {wild_badge}
                </div>
                <div style="display:flex;gap:0.25rem;flex-wrap:wrap">
                  <button type="button" class="btn-secondary agent-select-option" data-option="{opt}">Revise</button>
                  {approve_btn}
                </div>
              </div>
            </article>
            """
        )
    return f"""
    <section class="agent-posters-panel">
      <h2>Posters — round {detail.get("round") or 0}</h2>
      <div class="agent-flyer-grid">{"".join(cards)}</div>
    </section>
    """


def _chat_panel(*, initial_message: str, gig_label: str) -> str:
    chat_api = html.escape(route_path("/agent/api/chat"))
    gig_api_tpl = html.escape(route_path("/agent/api/gig/"))
    job_api_tpl = html.escape(route_path("/agent/api/gig/"))
    welcome = html.escape(initial_message)
    label = html.escape(gig_label or "Flyer Agent")
    return f"""
    <section class="agent-chat-panel" id="agent-chat-panel">
      <div class="agent-chat-head">Agent chat · {label}</div>
      <div class="agent-chat-log" id="agent-chat-log" aria-live="polite">
        <div class="agent-chat-msg agent">{welcome}</div>
      </div>
      <form class="agent-chat-compose" id="agent-chat-form">
        <textarea id="agent-chat-input" rows="2"
          placeholder="Ask about design, say generate, or describe revisions…"></textarea>
        <button type="submit" id="agent-chat-send">Send</button>
      </form>
    </section>
    <script>
    (function() {{
      var chatApi = "{chat_api}";
      var gigApiTpl = "{gig_api_tpl}";
      var jobApiTpl = "{job_api_tpl}";
      var logEl = document.getElementById("agent-chat-log");
      var form = document.getElementById("agent-chat-form");
      var input = document.getElementById("agent-chat-input");
      var sendBtn = document.getElementById("agent-chat-send");
      var gigInput = document.getElementById("agent-gig-id");
      var pollTimer = null;

      function appendMsg(role, text) {{
        var div = document.createElement("div");
        div.className = "agent-chat-msg " + role;
        div.textContent = text;
        logEl.appendChild(div);
        logEl.scrollTop = logEl.scrollHeight;
        return div;
      }}

      function token() {{
        return localStorage.getItem("session_token") || localStorage.getItem("session_id") || "";
      }}

      function authHeaders() {{
        return {{ "X-Session-ID": token() }};
      }}

      function gigId() {{
        return gigInput ? gigInput.value : "";
      }}

      function posterUrl(flyer, detail) {{
        var url = flyer.url || flyer.path || "";
        if (!url) return "";
        if (url.indexOf("?") >= 0) return url;
        var round = detail && detail.round ? detail.round : "";
        var stamp = (detail && detail.updated_at) ? detail.updated_at : round;
        return url + "?v=" + encodeURIComponent(round) + "&t=" + encodeURIComponent(String(stamp).slice(0, 32));
      }}

      function updateMeta(detail) {{
        if (!detail) return;
        var roundEl = document.getElementById("agent-gig-round");
        if (roundEl) roundEl.textContent = String(detail.round || 0);
      }}

      function renderPosters(detail) {{
        var panel = document.querySelector(".agent-posters-panel");
        if (!panel || !detail) return;
        var flyers = detail.flyers || [];
        if (!flyers.length) {{
          panel.innerHTML = '<h2>Posters</h2><div class="agent-empty-state">No posters yet — ask the agent to generate options, or use Generate above.</div>';
          return;
        }}
        var canApprove = detail.workflow !== "approved";
        var cards = flyers.map(function(f) {{
          var opt = f.option || "?";
          var url = posterUrl(f, detail);
          var approveBtn = canApprove
            ? '<button type="button" class="btn-approve agent-approve-option" data-option="' + opt + '">Approve</button>'
            : "";
          var wildBadge = f.is_wild
            ? '<span class="agent-wild-badge">Fully designed · experimental<br><span style="font-weight:400">Faces may not match</span></span>'
            : "";
          return '<article class="agent-flyer-card" data-option="' + opt + '">' +
            '<img src="' + url + '" alt="Option ' + opt + '" loading="lazy" />' +
            '<div class="flyer-cap"><div><strong>Option ' + opt + '</strong>' + wildBadge + '</div>' +
            '<div style="display:flex;gap:0.25rem;flex-wrap:wrap">' +
            '<button type="button" class="btn-secondary agent-select-option" data-option="' + opt + '">Revise</button>' +
            approveBtn + '</div></div></article>';
        }}).join("");
        panel.innerHTML = '<h2>Posters — round ' + (detail.round || 0) + '</h2><div class="agent-flyer-grid">' + cards + '</div>';
        updateMeta(detail);
        bindPosterButtons();
      }}

      function pathsMatchRound(detail, expectedRound) {{
        if (!expectedRound) return true;
        var flyers = detail.flyers || [];
        if (!flyers.length) return false;
        return flyers.every(function(f) {{
          var p = f.path || f.url || "";
          return p.indexOf("_r" + expectedRound) >= 0;
        }});
      }}

      function refreshGigDetailUntilRound(expectedRound, attempt) {{
        attempt = attempt || 0;
        return refreshGigDetail().then(function(data) {{
          var detail = data && data.detail;
          if (!detail) return data;
          if (!expectedRound || (detail.round >= expectedRound && pathsMatchRound(detail, expectedRound))) {{
            return data;
          }}
          if (attempt >= 10) return data;
          return new Promise(function(resolve) {{
            setTimeout(function() {{
              resolve(refreshGigDetailUntilRound(expectedRound, attempt + 1));
            }}, 600);
          }});
        }});
      }}

      function approveOption(opt) {{
        var id = gigId();
        if (!id || !opt) return;
        if (!confirm("Approve option " + opt + " for this gig?")) return;
        fetch(gigApiTpl + encodeURIComponent(id) + "/approve", {{
          method: "POST",
          headers: Object.assign({{ "Content-Type": "application/json" }}, authHeaders()),
          body: JSON.stringify({{ option: opt }})
        }}).then(function(r) {{ return r.json().then(function(data) {{ return {{ ok: r.ok, data: data }}; }}); }})
          .then(function(res) {{
            if (!res.ok) {{
              appendMsg("agent", res.data.detail || "Could not approve that option.");
              return;
            }}
            appendMsg("agent", "Approved option " + opt + ".");
            if (res.data.detail) renderPosters(res.data.detail);
          }})
          .catch(function() {{ appendMsg("agent", "Approve failed — try again."); }});
      }}

      function bindPosterButtons() {{
        document.querySelectorAll(".agent-select-option").forEach(function(btn) {{
          btn.addEventListener("click", function() {{
            var opt = btn.getAttribute("data-option");
            document.querySelectorAll(".agent-flyer-card").forEach(function(c) {{
              c.classList.toggle("selected", c.getAttribute("data-option") === opt);
            }});
            input.value = "I like option " + opt + ", but ";
            input.focus();
          }});
        }});
        document.querySelectorAll(".agent-approve-option").forEach(function(btn) {{
          btn.addEventListener("click", function() {{
            approveOption(btn.getAttribute("data-option"));
          }});
        }});
      }}

      function refreshGigDetail() {{
        var id = gigId();
        if (!id) return Promise.resolve(null);
        return fetch(gigApiTpl + encodeURIComponent(id), {{ headers: authHeaders() }})
          .then(function(r) {{ return r.ok ? r.json() : null; }})
          .then(function(data) {{
            if (data && data.detail) renderPosters(data.detail);
            return data;
          }});
      }}

      function stopPolling() {{
        if (pollTimer) {{
          clearInterval(pollTimer);
          pollTimer = null;
        }}
      }}

      function pollJob(jobInfo) {{
        var id = gigId();
        if (!id) return;
        stopPolling();
        var statusEl = appendMsg("agent", "Generating…");
        var sawRunning = false;
        var pollStartedAt = Date.now();
        pollTimer = setInterval(function() {{
          fetch(jobApiTpl + encodeURIComponent(id) + "/job", {{ headers: authHeaders() }})
            .then(function(r) {{ return r.json(); }})
            .then(function(status) {{
              if (status.status === "running") sawRunning = true;
              var msg = status.message || status.detail || status.status || "Working…";
              statusEl.textContent = msg.charAt(0).toUpperCase() + msg.slice(1);
              if (status.status === "done") {{
                if (!sawRunning && status.updated_at) {{
                  var doneAt = Date.parse(status.updated_at);
                  if (!isNaN(doneAt) && doneAt < pollStartedAt - 500) return;
                }}
                stopPolling();
                var expected = jobInfo && jobInfo.expected_round;
                refreshGigDetailUntilRound(expected).then(function(data) {{
                  var actualRound = data && data.detail ? data.detail.round : expected;
                  var suffix = actualRound ? (" Round " + actualRound + " is ready above.") : " Posters updated above.";
                  appendMsg("agent", "Done —" + suffix);
                }});
              }} else if (status.status === "error") {{
                stopPolling();
                appendMsg("agent", "Generation failed: " + (status.message || status.detail || "unknown error"));
              }}
            }})
            .catch(function() {{ /* keep polling */ }});
        }}, 1200);
      }}

      form.addEventListener("submit", function(ev) {{
        ev.preventDefault();
        var msg = (input.value || "").trim();
        if (!msg) return;
        appendMsg("user", msg);
        input.value = "";
        sendBtn.disabled = true;
        fetch(chatApi, {{
          method: "POST",
          headers: Object.assign({{ "Content-Type": "application/json" }}, authHeaders()),
          body: JSON.stringify({{ gig_id: gigId() || null, message: msg }})
        }}).then(function(r) {{ return r.json(); }}).then(function(data) {{
          appendMsg("agent", data.reply || "OK");
          if (data.job && data.job.started) {{
            if (data.job.type === "approve" && data.job.status === "approved") {{
              refreshGigDetail();
            }} else {{
              pollJob(data.job);
            }}
          }}
        }}).catch(function() {{
          appendMsg("agent", "Sorry, I could not reach the agent. Try again.");
        }}).finally(function() {{
          sendBtn.disabled = false;
          input.focus();
        }});
      }});

      bindPosterButtons();
    }})();
    </script>
    """


def render_login_page(*, band_tools_url: str = "/") -> str:
    from flyer_agent.session_sync import agent_session_sync_script

    home = html.escape(band_tools_url.rstrip("/") + "/")
    return (
        page_head("Flyer Agent — Sign In", extra_css=agent_css())
        + """
  <main class="page-main">
    <div class="login-panel">
      <h1>Flyer Agent</h1>
      <p class="lead">Sign in with Google to manage upcoming gig posters.</p>
      <p class="muted">Your session is shared with Band Tools. Sign in on the home page, then return here.</p>
      <a class="btn" href=\"""" + home + """\">Go to Band Tools to sign in</a>
      <p class="muted" style="margin-top:1rem" id="agent-auth-status">Checking session…</p>
    </div>
  </main>
"""
        + agent_session_sync_script(redirect_to=route_path("/agent"))
        + page_close()
    )


def render_agent_workspace(
    *,
    user: dict[str, Any],
    board: dict[str, Any],
    selected_gig_id: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
    recommendation: Optional[dict[str, Any]] = None,
) -> str:
    user_name = html.escape(user.get("name") or user.get("email") or "User")
    rec = recommendation or {"message": "Select a gig to begin."}
    event = (detail or {}).get("event") or {}
    gig_label = event.get("venue") or "Select a gig"

    if selected_gig_id and detail:
        welcome = (
            f"Hi {user.get('name') or 'there'} — I'm your concert poster agent. "
            f"{rec.get('message', '')} Ask me to generate, revise, or explain the design for this gig."
        )
    else:
        welcome = (
            f"Hi {user.get('name') or 'there'} — pick an upcoming gig from the left. "
            "I know your calendar, band photo, logo, and layout best practices."
        )

    sidebar = _sidebar_nav(board, selected_gig_id)
    meta = _meta_panel(detail, rec)
    posters = _posters_panel(detail)
    chat = _chat_panel(initial_message=welcome, gig_label=str(gig_label))

    count = board.get("count", 0)
    today = html.escape(str(board.get("today", "")))

    return (
        page_head("Flyer Agent", extra_css=agent_css())
        + site_nav(active="agent")
        + f"""
  <main class="page-main agent-workspace-wrap">
    <div class="agent-workspace">
      <aside class="agent-sidebar">
        <div class="agent-sidebar-head">
          <h2>Upcoming gigs</h2>
          <p class="muted">{count} shows · from {today}</p>
          <p class="muted">Signed in as {user_name}</p>
        </div>
        {sidebar}
      </aside>
      <div class="agent-main">
        {meta}
        {posters}
        {chat}
      </div>
    </div>
    <p class="muted" style="margin-top:0.75rem;font-size:0.82rem">
      <a href="{html.escape(route_path('/agent/catalog'))}">Design catalog</a> ·
      <a href="{html.escape(route_path('/agent/research'))}">Design research</a>
    </p>
  </main>
"""
        + page_close()
    )


def render_agent_dashboard(
    *,
    user: dict[str, Any],
    board: dict[str, Any],
    system: dict[str, Any],
) -> str:
    _ = system
    selected: Optional[str] = None
    detail = None
    recommendation = None
    gigs = board.get("gigs") or []
    if gigs:
        selected = gigs[0]["gig_id"]
        from flyer_agent.agent import FlyerAgent

        agent = FlyerAgent()
        detail = agent.gig_detail(selected)
        if detail:
            recommendation = agent.recommend_action(selected)
    return render_agent_workspace(
        user=user,
        board=board,
        selected_gig_id=selected,
        detail=detail,
        recommendation=recommendation,
    )


def render_gig_detail_page(
    *,
    user: dict[str, Any],
    detail: dict[str, Any],
    recommendation: dict[str, Any],
    board: Optional[dict[str, Any]] = None,
) -> str:
    if board is None:
        from flyer_agent.gig_board import build_agent_gig_board

        board = build_agent_gig_board()
    return render_agent_workspace(
        user=user,
        board=board,
        selected_gig_id=detail.get("gig_id"),
        detail=detail,
        recommendation=recommendation,
    )


def render_generating_page(gig_id: str, event: dict[str, Any]) -> str:
    from bridge.interactive import render_generating_page as base_generating

    return base_generating(gig_id, event).replace(
        "Back to gig list",
        "Back to Flyer Agent",
    ).replace(
        html.escape(route_path("/pick")),
        html.escape(route_path(f"/agent/gig/{gig_id}")),
    )


def render_catalog_page(entries: list[dict[str, Any]]) -> str:
    items = []
    for entry in entries:
        title = html.escape(entry.get("title", ""))
        notes = html.escape(entry.get("notes", ""))
        tags = ", ".join(html.escape(t) for t in (entry.get("tags") or []))
        items.append(
            f'<div class="catalog-item"><strong>{title}</strong><br/>'
            f'<span class="muted">{tags}</span><p>{notes}</p></div>'
        )
    grid = "".join(items) or '<p class="muted">Catalog is empty.</p>'
    return (
        page_head("Design Catalog — Flyer Agent", extra_css=agent_css())
        + site_nav(active="agent")
        + f"""
  <main class="page-main">
    <p><a href="{html.escape(route_path('/agent'))}">← Flyer Agent</a></p>
    <h1>Good design catalog</h1>
    <p class="lead">Reference designs the agent uses for inspiration and quality benchmarks.</p>
    <div class="catalog-grid">{grid}</div>
  </main>
"""
        + page_close()
    )


def render_research_page(findings: list[dict[str, Any]]) -> str:
    items = []
    for f in findings:
        topic = html.escape(f.get("topic", ""))
        summary = html.escape(f.get("summary", ""))
        tags = ", ".join(html.escape(t) for t in (f.get("tags") or []))
        items.append(
            f'<div class="catalog-item"><strong>{topic}</strong><br/>'
            f'<span class="muted">{tags}</span><p>{summary}</p></div>'
        )
    grid = "".join(items) or '<p class="muted">No research findings yet.</p>'
    return (
        page_head("Design Research — Flyer Agent", extra_css=agent_css())
        + site_nav(active="agent")
        + f"""
  <main class="page-main">
    <p><a href="{html.escape(route_path('/agent'))}">← Flyer Agent</a></p>
    <h1>Design research</h1>
    <p class="lead">Periodic background research on poster trends, venue context, and layout ideas.</p>
    <form method="post" action="{html.escape(route_path('/agent/research/refresh'))}">
      <button type="submit" class="btn-secondary">Refresh research now</button>
    </form>
    <div class="catalog-grid" style="margin-top:1rem">{grid}</div>
  </main>
"""
        + page_close()
    )
