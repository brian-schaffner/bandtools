"""Home dashboard and interactive gig picker pages."""

from __future__ import annotations

import html
import os
from typing import Any

from bridge.review import pick_action, pick_page_path, pick_regenerate_action, render_job_progress_page, review_page_path, route_path
from bridge.ui import home_css, page_close, page_head, picker_css, site_nav
from gig_calendar import get_cache_info, get_future_gigs, get_local_today
from state import can_regenerate, get_gig_state, has_existing_generation, is_approved

_PICKER_MAX_DAYS = int(os.getenv("GIG_FLYERS_PICKER_DAYS", "60"))


def _gig_status_label(gig_id: str) -> tuple[str, str]:
    record = get_gig_state(gig_id) or {}
    status = record.get("status", "new")
    if is_approved(gig_id):
        return "approved", "Approved"
    if status == "pending_review":
        return "pending", "Pending review"
    if record and (record.get("round", 0) > 0 or record.get("options")):
        return "in_progress", "In progress"
    if record:
        return "known", "Not started"
    return "new", "New"


def _badge_class(status_key: str) -> str:
    if status_key == "approved":
        return "badge badge-approved"
    if status_key == "pending":
        return "badge badge-pending"
    return "badge"


def build_picker_data(max_days: int = _PICKER_MAX_DAYS) -> dict[str, Any]:
    today = get_local_today()
    gigs = get_future_gigs(min_days=0, max_days=max_days, background_refresh=True)
    cache = get_cache_info()
    items: list[dict[str, Any]] = []
    for event in gigs:
        status_key, status_label = _gig_status_label(event.gig_id)
        record = get_gig_state(event.gig_id) or {}
        has_gen = has_existing_generation(event.gig_id)
        items.append(
            {
                "gig_id": event.gig_id,
                "date": event.event_date.isoformat(),
                "short_date": event.event_date.strftime("%b %d"),
                "time": event.time_label,
                "venue": event.venue,
                "title": event.title,
                "days_out": (event.event_date - today).days,
                "status_key": status_key,
                "status_label": status_label,
                "can_generate": not is_approved(event.gig_id) and not has_gen,
                "can_regenerate": can_regenerate(event.gig_id),
                "review_url": review_page_path(event.gig_id)
                if (record.get("options") or is_approved(event.gig_id))
                else None,
            }
        )
    return {
        "today": today.isoformat(),
        "max_days": max_days,
        "count": len(items),
        "gigs": items,
        "cache": {
            "fetched_at": cache.fetched_at,
            "is_stale": cache.is_stale,
            "source": cache.source,
            "age_seconds": cache.age_seconds,
        },
    }


def render_home_page() -> str:
    pick = html.escape(pick_page_path())
    from bridge.review import route_path

    shell_studio = html.escape(route_path("/shell"))
    return (
        page_head("Gig Flyers", extra_css=home_css())
        + site_nav(active="home")
        + f"""
  <main class="page-main">
    <h1>Gig Flyers</h1>
    <p class="lead">Generate promoter-style flyer options from your gig calendar — part of Band Tools.</p>
    <div class="mode-cards">
      <article class="mode-card">
        <h2>Mode 1 — Auto</h2>
        <p>Daily scan for gigs 21–28 days out. New gigs get 3 flyer options and an iMessage review link automatically.</p>
        <p><code>python3 scripts/auto_scan.py</code> or Cursor daily automation at 9 AM.</p>
      </article>
      <article class="mode-card mode-card-featured">
        <h2>Mode 2 — Interactive</h2>
        <p>Pick any upcoming gig from the live calendar and trigger flyer generation on demand.</p>
        <a class="btn btn-block" href="{pick}">Choose a gig →</a>
      </article>
      <article class="mode-card mode-card-featured">
        <h2>Flyer Agent</h2>
        <p>Sign in with Google, pick an upcoming gig, and generate or revise posters with an expert design agent.</p>
        <a class="btn btn-block" href="{html.escape(route_path("/agent"))}">Open Flyer Agent →</a>
      </article>
      <article class="mode-card mode-card-featured">
        <h2>Shell Design Studio</h2>
        <p>Two-pass AI poster design: pick a reference shell, generate a placeholder design, then personalize with your gig, band photo, and logo — all in the browser.</p>
        <a class="btn btn-purple btn-block" href="{shell_studio}">Open shell studio →</a>
      </article>
      <article class="mode-card">
        <h2>Review</h2>
        <p>Open a review link from iMessage, or browse gigs after generation.</p>
        <a class="btn btn-secondary btn-block" href="{pick}">Browse gigs &amp; reviews</a>
      </article>
    </div>
  </main>
"""
        + page_close()
    )


def _gig_actions_html(gig: dict[str, Any]) -> str:
    if gig.get("can_regenerate"):
        parts = [
            f'<form method="post" action="{html.escape(pick_regenerate_action(gig["gig_id"]))}"'
            f' onsubmit="return confirm(\'Regenerate 3 fresh options from scratch?\');">'
            f'<button type="submit" class="btn-purple">Regenerate</button></form>'
        ]
        if gig.get("review_url"):
            parts.append(
                f'<a class="btn btn-secondary" href="{html.escape(gig["review_url"])}">Review</a>'
            )
        return f'<div class="gig-card-actions">{"".join(parts)}</div>'
    if gig.get("can_generate"):
        return (
            f'<div class="gig-card-actions">'
            f'<form method="post" action="{html.escape(pick_action(gig["gig_id"]))}">'
            f'<button type="submit">Generate 3 options</button></form>'
            f"</div>"
        )
    if gig.get("review_url"):
        return (
            f'<div class="gig-card-actions">'
            f'<a class="btn" href="{html.escape(gig["review_url"])}">Open review</a>'
            f"</div>"
        )
    return '<div class="gig-card-actions"><span class="muted">No action</span></div>'


def render_picker_page(data: dict[str, Any]) -> str:
    cards: list[str] = []
    table_rows: list[str] = []
    for gig in data.get("gigs", []):
        venue = html.escape(gig["venue"])
        short_date = html.escape(gig["short_date"])
        time_label = html.escape(gig.get("time") or "TBA")
        title = html.escape(gig.get("title") or "")
        status = html.escape(gig["status_label"])
        status_key = gig["status_key"]
        days_out = gig["days_out"]
        badge_cls = _badge_class(status_key)
        actions = _gig_actions_html(gig)

        cards.append(
            f"""
            <article class="gig-card status-{html.escape(status_key)}">
              <div class="gig-card-head">
                <div class="gig-card-date">{short_date}</div>
                <div class="gig-card-venue">
                  <strong>{venue}</strong>
                  <span class="muted">{title}</span>
                </div>
              </div>
              <div class="gig-card-meta">
                <span class="muted">{time_label}</span>
                <span class="muted">{days_out}d out</span>
                <span class="{badge_cls}">{status}</span>
              </div>
              {actions}
            </article>
            """
        )
        table_rows.append(
            f"""
            <tr class="status-{html.escape(status_key)}">
              <td>{short_date}</td>
              <td>{time_label}</td>
              <td><strong>{venue}</strong><br /><span class="muted">{title}</span></td>
              <td>{days_out}d</td>
              <td><span class="{badge_cls}">{status}</span></td>
              <td>{actions}</td>
            </tr>
            """
        )

    cache_note = ""
    cache = data.get("cache") or {}
    if cache.get("fetched_at"):
        fetched = html.escape(str(cache["fetched_at"]))
        stale = bool(cache.get("is_stale"))
        if stale:
            cache_note = (
                f'<p class="cache-note muted">Calendar cached at {fetched} '
                f"(stale — live site unreachable; refreshing in background)</p>"
            )
        else:
            cache_note = f'<p class="cache-note muted">Calendar cached at {fetched}</p>'

    empty = '<p class="muted">No upcoming gigs found.</p>'
    cards_html = "".join(cards) or empty
    table_html = "".join(table_rows) or "<tr><td colspan='6'>No upcoming gigs found.</td></tr>"

    return (
        page_head("Pick a gig — Gig Flyers", extra_css=picker_css())
        + site_nav(active="pick")
        + f"""
  <main class="page-main">
    <h1>Pick a gig</h1>
    <p class="meta">Live calendar · next {data.get("max_days", 60)} days · today {html.escape(data.get("today", ""))}</p>
    <div class="gig-cards">{cards_html}</div>
    <table class="picker-table">
      <thead>
        <tr><th>Date</th><th>Time</th><th>Venue</th><th>In</th><th>Status</th><th></th></tr>
      </thead>
      <tbody>{table_html}</tbody>
    </table>
    {cache_note}
  </main>
"""
        + page_close()
    )


def render_generating_page(gig_id: str, event: dict[str, Any]) -> str:
    return render_job_progress_page(
        gig_id,
        event,
        heading="Generating flyer options…",
        subtitle="Creating 3 options via OpenAI. This usually takes 2–3 minutes.",
        back_href=pick_page_path(),
        back_label="Back to gig list",
    )
