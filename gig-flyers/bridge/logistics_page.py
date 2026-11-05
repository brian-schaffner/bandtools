"""On-demand performance-day logistics: pick a published gig, view / copy / email its day schedule."""

from __future__ import annotations

import html
import os
from dataclasses import replace
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import Form
from fastapi.responses import HTMLResponse, PlainTextResponse

from bridge.review import route_path
from bridge.routing import add_get, add_post
from bridge.ui import page_close, page_head, picker_css, site_nav
from gig_calendar import CalendarUnavailableError, GigEvent, find_gig_by_id, get_future_gigs, get_local_today
from logistics.delivery import email_configured, markdown_to_html, recipient, send_schedule_email
from logistics.drive_time import DriveEstimate
from logistics.profiles import load_config
from logistics.render import render_markdown, render_text
from logistics.schedule import GigInput, LogisticsSchedule, build_schedule, parse_clock

_LIST_MAX_DAYS = int(os.getenv("GIG_LOGISTICS_LIST_DAYS", os.getenv("GIG_FLYERS_PICKER_DAYS", "60")))


def logistics_page_path() -> str:
    return route_path("/logistics")


def logistics_gig_path(gig_id: str, **params: str) -> str:
    query = urlencode({k: v for k, v in params.items() if v})
    path = route_path(f"/logistics/{gig_id}")
    return f"{path}?{query}" if query else path


def logistics_css() -> str:
    return """
    .schedule-layout { display: grid; gap: 1.25rem; }
    @media (min-width: 900px) { .schedule-layout { grid-template-columns: minmax(0, 1fr) 300px; align-items: start; } }
    .schedule-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.1rem 1.25rem;
      line-height: 1.6;
      font-size: 1rem;
      overflow-wrap: anywhere;
    }
    .side-panel { display: flex; flex-direction: column; gap: 1rem; }
    .side-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
    }
    .side-box h2 { font-size: 1rem; margin: 0; }
    .side-box label { font-size: 0.85rem; color: var(--muted); display: flex; flex-direction: column; gap: 0.25rem; }
    .side-box input { padding: 0.5rem; border: 1px solid var(--border); border-radius: 8px; font-size: 0.95rem; }
    .side-box .btn, .side-box button { width: 100%; }
    .flash { border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 1rem; }
    .flash-ok { background: var(--pass-bg); color: var(--pass-text); }
    .flash-err { background: var(--warn-bg); color: var(--warn-text); }
    .badge-excluded { opacity: 0.75; }
    .picker-table td:first-child, .picker-table .btn, .picker-table .badge { white-space: nowrap; }
    """


def _overrides(end: str, drive: str) -> tuple[Optional[str], Optional[int], list[str]]:
    errors: list[str] = []
    end_value = (end or "").strip() or None
    if end_value and parse_clock(end_value) is None:
        errors.append(f"Could not read end time {end_value!r} — use a time like 11:00 pm.")
        end_value = None
    drive_minutes: Optional[int] = None
    if (drive or "").strip():
        try:
            drive_minutes = int(drive)
            if not 0 < drive_minutes <= 600:
                raise ValueError
        except ValueError:
            errors.append(f"Drive minutes must be a whole number between 1 and 600 (got {drive!r}).")
            drive_minutes = None
    return end_value, drive_minutes, errors


def build_on_demand(event: GigEvent, *, end: Optional[str] = None, drive_minutes: Optional[int] = None) -> LogisticsSchedule:
    gig = GigInput.from_event(event)
    if end:
        gig = replace(gig, end=parse_clock(end))
    drive = DriveEstimate(drive_minutes, "entered", True) if drive_minutes else None
    return build_schedule(gig, drive=drive)


def _event_label(event: GigEvent) -> str:
    return f"{event.event_date:%a %b} {event.event_date.day} · {event.venue}"


def render_logistics_list_page(events: list[GigEvent], *, today_label: str, error: str = "") -> str:
    config = load_config()
    cards: list[str] = []
    rows: list[str] = []
    for event in events:
        excluded = config.is_excluded(event.title)
        href = html.escape(logistics_gig_path(event.gig_id))
        venue = html.escape(event.venue)
        title = html.escape(event.title)
        when = html.escape(f"{event.event_date:%a %b} {event.event_date.day}")
        start = html.escape(event.time_label or "TBA")
        end = html.escape(event.end_time_label)
        time_label = f"{start}–{end}" if end else start
        badge = (
            '<span class="badge badge-excluded">Skipped in weekly run</span>'
            if excluded
            else ('<span class="badge badge-approved">Venue profile</span>' if config.match_venue(event.title) else '<span class="badge">Standard timing</span>')
        )
        button = f'<a class="btn" href="{href}">Build day schedule</a>'
        cards.append(
            f"""
            <article class="gig-card">
              <div class="gig-card-head">
                <div class="gig-card-date">{when}</div>
                <div class="gig-card-venue"><strong>{venue}</strong><span class="muted">{title}</span></div>
              </div>
              <div class="gig-card-meta"><span class="muted">{time_label}</span>{badge}</div>
              <div class="gig-card-actions">{button}</div>
            </article>"""
        )
        rows.append(
            f"""
            <tr>
              <td>{when}</td><td>{time_label}</td>
              <td><strong>{venue}</strong><br /><span class="muted">{title}</span></td>
              <td>{badge}</td><td>{button}</td>
            </tr>"""
        )
    empty = '<p class="muted">No upcoming gigs on the published schedule.</p>'
    error_html = f'<div class="flash flash-err">{html.escape(error)}</div>' if error else ""
    return (
        page_head("Day schedule — Band Tools", extra_css=picker_css() + logistics_css())
        + site_nav(active="logistics")
        + f"""
  <main class="page-main">
    <h1>Performance-day schedule</h1>
    <p class="meta">Pick a gig from the published calendar to build its departure &amp; setup schedule · today {html.escape(today_label)}</p>
    {error_html}
    <div class="gig-cards">{''.join(cards) or empty}</div>
    <table class="picker-table">
      <thead><tr><th>Date</th><th>Time</th><th>Venue</th><th>Timing</th><th></th></tr></thead>
      <tbody>{''.join(rows) or "<tr><td colspan='5'>No upcoming gigs on the published schedule.</td></tr>"}</tbody>
    </table>
  </main>
"""
        + page_close()
    )


def render_logistics_gig_page(
    event: GigEvent,
    schedule: LogisticsSchedule,
    *,
    end: str = "",
    drive: str = "",
    flash: str = "",
    flash_ok: bool = True,
) -> str:
    gig_id = event.gig_id
    text_href = html.escape(route_path(f"/logistics/{gig_id}/text") + (f"?{urlencode({k: v for k, v in {'end': end, 'drive': drive}.items() if v})}" if (end or drive) else ""))
    form_action = html.escape(route_path(f"/logistics/{gig_id}"))
    email_action = html.escape(route_path(f"/logistics/{gig_id}/email"))
    plain = render_text(schedule)
    flash_html = f'<div class="flash {"flash-ok" if flash_ok else "flash-err"}">{html.escape(flash)}</div>' if flash else ""
    if email_configured():
        email_box = f"""
        <form method="post" action="{email_action}" class="side-box">
          <h2>Email</h2>
          <input type="hidden" name="end" value="{html.escape(end)}" />
          <input type="hidden" name="drive" value="{html.escape(drive)}" />
          <button type="submit" class="btn">Email to {html.escape(recipient())}</button>
        </form>"""
    else:
        email_box = """
        <div class="side-box">
          <h2>Email</h2>
          <p class="muted">Email isn’t configured on this server yet (needs SMTP_HOST, SMTP_USER, SMTP_PASSWORD).</p>
        </div>"""
    est_drive = schedule.drive.minutes
    return (
        page_head(f"Day schedule — {_event_label(event)}", extra_css=logistics_css())
        + site_nav(active="logistics", back_href=logistics_page_path(), back_label="All gigs")
        + f"""
  <main class="page-main">
    <h1>{html.escape(_event_label(event))}</h1>
    <p class="meta">{html.escape(event.title)} · published {html.escape(event.time_label or "TBA")}{html.escape(" – " + event.end_time_label if event.end_time_label else "")}</p>
    {flash_html}
    <div class="schedule-layout">
      <section class="schedule-card" id="schedule">{markdown_to_html(render_markdown(schedule))}</section>
      <aside class="side-panel">
        <div class="side-box">
          <h2>Share</h2>
          <button type="button" class="btn" id="copy-schedule">Copy text</button>
          <a class="btn btn-secondary" href="{text_href}">Download .txt</a>
        </div>
        {email_box}
        <form method="get" action="{form_action}" class="side-box">
          <h2>Adjust</h2>
          <label>End time <input name="end" value="{html.escape(end)}" placeholder="e.g. 11:00 pm" /></label>
          <label>Drive minutes (one way) <input name="drive" type="number" min="1" max="600" value="{html.escape(drive)}" placeholder="{est_drive}" /></label>
          <button type="submit" class="btn btn-secondary">Rebuild schedule</button>
        </form>
      </aside>
    </div>
    <textarea id="schedule-text" hidden>{html.escape(plain)}</textarea>
  </main>
  <script>
    document.addEventListener("click", function (ev) {{
      var btn = ev.target.closest("#copy-schedule");
      if (!btn) return;
      var text = document.getElementById("schedule-text").value;
      function done(label) {{
        btn.textContent = label;
        setTimeout(function () {{ btn.textContent = "Copy text"; }}, 2500);
      }}
      function fallback() {{
        var area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        var ok = false;
        try {{ ok = document.execCommand("copy"); }} catch (e) {{ ok = false; }}
        document.body.removeChild(area);
        done(ok ? "Copied!" : "Copy failed — use Download");
      }}
      if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(text).then(function () {{ done("Copied!"); }}, fallback);
      }} else {{
        fallback();
      }}
    }});
  </script>
"""
        + page_close()
    )


def _not_found_page(gig_id: str) -> HTMLResponse:
    body = (
        page_head("Gig not found — Band Tools", extra_css=logistics_css())
        + site_nav(active="logistics", back_href=logistics_page_path(), back_label="All gigs")
        + f"""
  <main class="page-main">
    <h1>Gig not found</h1>
    <p class="meta">{html.escape(gig_id)} isn’t on the published schedule. Pick another gig.</p>
  </main>
"""
        + page_close()
    )
    return HTMLResponse(body, status_code=404)


def register_logistics_routes(app: Any) -> None:
    @add_get(app, "/logistics", response_class=HTMLResponse)
    async def logistics_list() -> HTMLResponse:
        today = get_local_today()
        try:
            events = get_future_gigs(min_days=0, max_days=_LIST_MAX_DAYS, background_refresh=True)
            error = ""
        except CalendarUnavailableError as exc:
            events, error = [], str(exc)
        return HTMLResponse(render_logistics_list_page(events, today_label=today.isoformat(), error=error))

    @add_get(app, "/logistics/{gig_id}/text", response_class=PlainTextResponse)
    async def logistics_text(gig_id: str, end: str = "", drive: str = ""):
        event = find_gig_by_id(gig_id)
        if not event:
            return PlainTextResponse("Gig not found", status_code=404)
        end_value, drive_minutes, _ = _overrides(end, drive)
        schedule = build_on_demand(event, end=end_value, drive_minutes=drive_minutes)
        return PlainTextResponse(
            render_text(schedule),
            headers={"Content-Disposition": f'attachment; filename="{gig_id}_day-schedule.txt"'},
        )

    @add_get(app, "/logistics/{gig_id}", response_class=HTMLResponse)
    async def logistics_gig(gig_id: str, end: str = "", drive: str = "") -> HTMLResponse:
        event = find_gig_by_id(gig_id)
        if not event:
            return _not_found_page(gig_id)
        end_value, drive_minutes, errors = _overrides(end, drive)
        schedule = build_on_demand(event, end=end_value, drive_minutes=drive_minutes)
        return HTMLResponse(
            render_logistics_gig_page(
                event,
                schedule,
                end=end_value or "",
                drive=str(drive_minutes or ""),
                flash=" ".join(errors),
                flash_ok=not errors,
            )
        )

    @add_post(app, "/logistics/{gig_id}/email", response_class=HTMLResponse)
    async def logistics_email(gig_id: str, end: str = Form(""), drive: str = Form("")) -> HTMLResponse:
        event = find_gig_by_id(gig_id)
        if not event:
            return _not_found_page(gig_id)
        end_value, drive_minutes, _ = _overrides(end, drive)
        schedule = build_on_demand(event, end=end_value, drive_minutes=drive_minutes)
        try:
            sent_to = send_schedule_email(schedule)
            flash, ok = f"Emailed to {sent_to}.", True
        except Exception as exc:  # noqa: BLE001
            flash, ok = f"Email failed: {exc}", False
        return HTMLResponse(
            render_logistics_gig_page(
                event, schedule, end=end_value or "", drive=str(drive_minutes or ""), flash=flash, flash_ok=ok
            ),
            status_code=200 if ok else 502,
        )
