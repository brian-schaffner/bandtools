"""Flyer Agent HTML UI."""

from __future__ import annotations

import html
import json
from typing import Any, Optional

from bridge.review import asset_url, review_page_path, route_path
from bridge.ui import base_css, page_close, page_head, site_nav


def agent_css() -> str:
    return base_css() + """
    .agent-hero {
      background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4c1d95 100%);
      color: #fff;
      border-radius: 16px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.25rem;
      box-shadow: 0 8px 24px rgba(30,27,75,0.25);
    }
    .agent-hero h1 { color: #fff; margin-bottom: 0.35rem; }
    .agent-hero .lead { color: rgba(255,255,255,0.85); margin-bottom: 0; }
    .agent-user { font-size: 0.9rem; color: rgba(255,255,255,0.75); margin-top: 0.5rem; }
    .source-badge {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      margin-right: 0.35rem;
    }
    .source-background { background: #dbeafe; color: #1d4ed8; }
    .source-interactive { background: #fef3c7; color: #b45309; }
    .source-agent { background: #ede9fe; color: #6d28d9; }
    .source-none { background: #f3f4f6; color: #6b7280; }
    .gig-agent-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 0.75rem;
    }
    .gig-agent-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    .gig-agent-head { display: flex; justify-content: space-between; gap: 0.75rem; align-items: flex-start; }
    .gig-agent-meta { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.5rem 0; }
    .flyer-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }
    .flyer-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
    .flyer-card img { width: 100%; display: block; aspect-ratio: 2/3; object-fit: cover; background: #eee; }
    .flyer-card-body { padding: 0.75rem; }
    .agent-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem; }
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
    .recommendation {
      background: #f0fdf4;
      border: 1px solid #86efac;
      border-radius: 10px;
      padding: 0.75rem 1rem;
      margin: 1rem 0;
      color: #166534;
    }
    .catalog-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; }
    .catalog-item { background: var(--surface-2); border-radius: 8px; padding: 0.75rem; font-size: 0.9rem; }
    textarea.feedback-input { width: 100%; min-height: 80px; padding: 0.5rem; border-radius: 8px; border: 1px solid var(--border); }
    """


def _source_badge(source_key: str, label: str) -> str:
    cls = f"source-badge source-{html.escape(source_key)}"
    return f'<span class="{cls}">{html.escape(label)}</span>'


def render_login_page(*, band_tools_url: str = "/") -> str:
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
  <script>
  (function(){
    var token = localStorage.getItem('session_token') || localStorage.getItem('session_id');
    var status = document.getElementById('agent-auth-status');
    if (!token || token === 'guest-session') {
      status.textContent = 'Not signed in yet.';
      return;
    }
    fetch('""" + html.escape(route_path("/agent/api/session")) + """', {
      headers: { 'X-Session-ID': token }
    }).then(function(r){ return r.json(); }).then(function(d){
      if (d.authenticated) {
        window.location.href = '""" + html.escape(route_path("/agent")) + """';
      } else {
        status.textContent = 'Session expired — sign in again.';
      }
    }).catch(function(){ status.textContent = 'Could not verify session.'; });
  })();
  </script>
"""
        + page_close()
    )


def render_agent_dashboard(
    *,
    user: dict[str, Any],
    board: dict[str, Any],
    system: dict[str, Any],
) -> str:
    cards: list[str] = []
    for gig in board.get("gigs", []):
        venue = html.escape(gig["venue"])
        short_date = html.escape(gig["short_date"])
        time_label = html.escape(gig.get("time") or "TBA")
        workflow = html.escape(gig.get("workflow_label", ""))
        source_badge = _source_badge(gig.get("generation_source", "none"), gig.get("generation_source_label", ""))
        gig_url = html.escape(route_path(f"/agent/gig/{gig['gig_id']}"))
        cards.append(
            f"""
            <article class="gig-agent-card">
              <div class="gig-agent-head">
                <div>
                  <strong>{short_date}</strong> · {venue}
                  <div class="muted">{time_label} · {gig['days_out']}d out</div>
                </div>
                <a class="btn btn-secondary" href="{gig_url}">Open →</a>
              </div>
              <div class="gig-agent-meta">
                {source_badge}
                <span class="badge">{workflow}</span>
              </div>
            </article>
            """
        )

    cards_html = "".join(cards) or '<p class="muted">No upcoming gigs in the calendar window.</p>'
    user_name = html.escape(user.get("name") or user.get("email") or "User")
    expertise = system.get("expertise") or {}
    band = html.escape(str(expertise.get("band", "Band")))

    return (
        page_head("Flyer Agent", extra_css=agent_css())
        + site_nav(active="agent")
        + f"""
  <main class="page-main">
    <div class="agent-hero">
      <h1>Flyer Agent</h1>
      <p class="lead">Expert concert poster design for {band} — upcoming gigs, band assets, and layout best practices.</p>
      <p class="agent-user">Signed in as {user_name}</p>
    </div>
    <h2>Upcoming gigs</h2>
    <p class="meta">Select a gig to view existing posters, generate new options, revise, or regenerate.</p>
    <div class="gig-agent-list">{cards_html}</div>
    <p class="muted"><a href="{html.escape(route_path('/agent/catalog'))}">Design catalog</a> ·
    <a href="{html.escape(route_path('/agent/research'))}">Design research</a></p>
  </main>
"""
        + page_close()
    )


def render_gig_detail_page(
    *,
    user: dict[str, Any],
    detail: dict[str, Any],
    recommendation: dict[str, Any],
) -> str:
    event = detail.get("event") or {}
    venue = html.escape(event.get("venue") or detail.get("gig_id", ""))
    short_date = html.escape(event.get("short_date") or event.get("date") or "")
    gig_id = html.escape(detail["gig_id"])
    rec_msg = html.escape(recommendation.get("message", ""))
    source_badge = _source_badge(detail.get("generation_source", "none"), detail.get("generation_source_label", ""))

    flyer_cards: list[str] = []
    for flyer in detail.get("flyers") or []:
        opt = html.escape(flyer["option"])
        img_url = html.escape(asset_url(flyer["path"]))
        flyer_cards.append(
            f"""
            <div class="flyer-card">
              <img src="{img_url}" alt="Option {opt}" loading="lazy" />
              <div class="flyer-card-body">
                <strong>Option {opt}</strong>
              </div>
            </div>
            """
        )
    flyers_html = "".join(flyer_cards) or '<p class="muted">No flyer images yet.</p>'

    actions: list[str] = []
    if detail.get("can_generate"):
        actions.append(
            f'<form method="post" action="{html.escape(route_path(f"/agent/gig/{detail["gig_id"]}/generate"))}">'
            f'<button type="submit">Generate 3 options</button></form>'
        )
    if detail.get("can_regenerate"):
        actions.append(
            f'<form method="post" action="{html.escape(route_path(f"/agent/gig/{detail["gig_id"]}/regenerate"))}"'
            f' onsubmit="return confirm(\'Regenerate fresh options from scratch?\');">'
            f'<button type="submit" class="btn-purple">Regenerate</button></form>'
        )
    if detail.get("can_revise") and detail.get("flyers"):
        review = html.escape(review_page_path(detail["gig_id"]))
        actions.append(f'<a class="btn" href="{review}">Full review UI</a>')

    revise_form = ""
    if detail.get("can_revise") and detail.get("flyers"):
        options = "".join(
            f'<option value="{html.escape(f["option"])}">{html.escape(f["option"])}</option>'
            for f in detail["flyers"]
        )
        revise_form = f"""
        <section style="margin-top:1.5rem">
          <h2>Revise an option</h2>
          <form method="post" action="{html.escape(route_path(f"/agent/gig/{detail['gig_id']}/revise"))}">
            <label>Option<br/><select name="option">{options}</select></label><br/><br/>
            <label>Feedback<br/><textarea class="feedback-input" name="feedback" required
              placeholder="e.g. Make the headline larger, warmer mustard background"></textarea></label><br/>
            <button type="submit" class="btn-secondary">Revise with feedback</button>
          </form>
        </section>
        """

    actions_html = "".join(actions) or '<span class="muted">No actions available</span>'

    return (
        page_head(f"{short_date} @ {venue} — Flyer Agent", extra_css=agent_css())
        + site_nav(active="agent")
        + f"""
  <main class="page-main">
    <p><a href="{html.escape(route_path('/agent'))}">← All gigs</a></p>
    <h1>{short_date} @ {venue}</h1>
    <div class="gig-agent-meta">{source_badge} <span class="badge">{html.escape(detail.get('workflow_label',''))}</span></div>
    <div class="recommendation">{rec_msg}</div>
    <div class="agent-actions">{actions_html}</div>
    <h2>Current flyers</h2>
    <div class="flyer-grid">{flyers_html}</div>
    {revise_form}
  </main>
"""
        + page_close()
    )


def render_generating_page(gig_id: str, event: dict[str, Any]) -> str:
    from bridge.interactive import render_generating_page as base_generating

    return base_generating(gig_id, event).replace(
        "Back to gig list",
        "Back to Flyer Agent",
    ).replace(
        html.escape(route_path("/pick")),
        html.escape(route_path("/agent")),
    )


def render_catalog_page(entries: list[dict[str, Any]]) -> str:
    items = []
    for entry in entries:
        title = html.escape(entry.get("title", ""))
        notes = html.escape(entry.get("notes", ""))
        tags = ", ".join(html.escape(t) for t in (entry.get("tags") or []))
        items.append(f'<div class="catalog-item"><strong>{title}</strong><br/><span class="muted">{tags}</span><p>{notes}</p></div>')
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
        items.append(f'<div class="catalog-item"><strong>{topic}</strong><br/><span class="muted">{tags}</span><p>{summary}</p></div>')
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
