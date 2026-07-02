"""Prototype iteration UI — rank 3, feedback, next 3 until success or forfeit."""

from __future__ import annotations

import html
import json
from typing import Any, Optional

from bridge.review import asset_url, pick_page_path, review_page_path, route_path
from bridge.ui import page_close, page_head, review_css, site_nav
from gig_resolve import is_placeholder_gig_id, load_event_dict
from prototype_session import get_prototype_session, prototype_max_rounds
from state import get_gig_state


def prototype_page_path(gig_id: str) -> str:
    return route_path(f"/prototype/{gig_id}")


def prototype_start_action(gig_id: str) -> str:
    return route_path(f"/prototype/{gig_id}/start")


def prototype_submit_action(gig_id: str) -> str:
    return route_path(f"/prototype/{gig_id}/submit")


def _tag_chips(tags: dict[str, str]) -> str:
    skip = {"tier", "wild"}
    chips = []
    for key, value in sorted(tags.items()):
        if key in skip or not value:
            continue
        label = html.escape(f"{key}: {value.replace('_', ' ')}")
        chips.append(f'<span class="tag-chip">{label}</span>')
    return " ".join(chips) if chips else '<span class="muted">—</span>'


def render_prototype_page(gig_id: str) -> str:
    if is_placeholder_gig_id(gig_id):
        pick = html.escape(pick_page_path())
        return (
            page_head("Prototype — invalid link", extra_css=review_css())
            + site_nav(active="prototype", back_href=pick, back_label="Pick gig")
            + f"""
  <main class="page-main">
    <h1>Invalid prototype link</h1>
    <p>This URL is a template placeholder, not a real gig.</p>
    <p class="muted">Open <strong>Pick a gig</strong>, generate or review flyers, then use
       <strong>Rapid prototype mode</strong> from that gig's review page.</p>
    <p><a class="btn btn-block" href="{pick}">Choose a gig →</a></p>
  </main>
"""
            + page_close()
        )

    record = get_gig_state(gig_id) or {}
    event = record.get("event") or load_event_dict(gig_id) or {}
    session = get_prototype_session(gig_id)
    status = session.get("status", "idle")
    proto_round = int(session.get("round") or 0)
    max_rounds = int(session.get("max_rounds") or prototype_max_rounds())
    options = session.get("options") or {}

    venue = html.escape(event.get("venue", "Venue TBA"))
    short_date = html.escape(event.get("short_date") or event.get("date", ""))
    band = html.escape(event.get("band", "Lindsey Lane Band"))

    if status in ("idle", "") or not options:
        body = f"""
        <section class="prototype-intro">
          <h2>Rapid prototype mode</h2>
          <p>We generate <strong>3 flyer directions</strong>. You rank them and leave feedback.
             The next batch of 3 is shaped by what you liked — up to {max_rounds} rounds, then you
             pick a winner or call it quits.</p>
          <p class="muted">Rules can be bent on purpose. Low scores and validation warnings are OK here.</p>
          <form method="post" action="{html.escape(prototype_start_action(gig_id))}">
            <button type="submit" class="btn btn-purple btn-block">Start prototype round 1</button>
          </form>
          <p style="margin-top:1rem"><a href="{html.escape(review_page_path(gig_id))}">← Standard A/B/C review</a></p>
        </section>
        """
    elif status == "success":
        slot = html.escape(str(session.get("winner_slot") or ""))
        body = f"""
        <div class="approved-banner">
          <p><strong>Prototype complete</strong> — winner slot {slot} approved.</p>
          <p><a class="btn btn-green" href="{html.escape(review_page_path(gig_id))}">View in review</a></p>
        </div>
        """
    elif status == "forfeit":
        body = """
        <div class="warn-banner">
          <p><strong>Prototype stopped</strong> — no winner this round.</p>
          <p><a class="btn btn-block" href="{review}">Back to standard review</a></p>
        </div>
        """.replace("{review}", html.escape(review_page_path(gig_id)))
    else:
        cards = []
        for slot in ("1", "2", "3"):
            opt = options.get(slot, {})
            rel = opt.get("path_rel", "")
            img = (
                f'<img class="flyer-img" src="{html.escape(asset_url(rel))}" alt="Prototype {slot}" loading="lazy" />'
                if rel
                else '<p class="muted">Render failed</p>'
            )
            label = html.escape(opt.get("label") or f"Option {slot}")
            score = opt.get("layout_score")
            score_html = f'<span class="muted">Layout {score:.1f}/10</span>' if score else ""
            wild = '<span class="tag-chip wild">rule-breaker</span>' if opt.get("wild") else ""
            issues = opt.get("validation_issues") or []
            issues_html = ""
            if issues:
                issues_html = f'<p class="muted small">Notes: {html.escape("; ".join(issues[:2]))}</p>'
            cards.append(
                f"""
                <article class="prototype-card" data-slot="{slot}">
                  <h3>#{slot} — {label} {wild}</h3>
                  {score_html}
                  <div class="tag-row">{_tag_chips(opt.get("tags") or {})}</div>
                  {img}
                  {issues_html}
                  <label>Rank
                    <select name="rank_{slot}" required>
                      <option value="">—</option>
                      <option value="1">1st (best)</option>
                      <option value="2">2nd</option>
                      <option value="3">3rd</option>
                    </select>
                  </label>
                  <label class="winner-pick">
                    <input type="radio" name="winner_slot" value="{slot}" /> This one wins
                  </label>
                </article>
                """
            )

        rounds_left = max(0, max_rounds - proto_round)
        body = f"""
        <section class="prototype-round">
          <p class="round-badge">Round <strong>{proto_round}</strong> of {max_rounds}
            · {rounds_left} round(s) left after this</p>
          <p class="muted">Rank all three (1st / 2nd / 3rd), add feedback, then continue or approve a winner.</p>
          <form method="post" action="{html.escape(prototype_submit_action(gig_id))}" class="prototype-form">
            <div class="options-grid prototype-grid">{''.join(cards)}</div>
            <label class="feedback-block">
              Feedback for the next batch
              <textarea name="feedback" rows="4" placeholder="e.g. liked the duotone red, hate the stamp, more handbill less wild…"></textarea>
            </label>
            <div class="prototype-actions">
              <button type="submit" name="action" value="next" class="btn btn-purple">Next 3 →</button>
              <button type="submit" name="action" value="approve" class="btn btn-green">Approve winner</button>
              <button type="submit" name="action" value="forfeit" class="btn btn-muted"
                      onclick="return confirm('Stop prototyping this gig?');">Give up</button>
            </div>
          </form>
        </section>
        """

    history = session.get("round_history") or []
    history_html = ""
    if history:
        rows = []
        for h in reversed(history):
            rnd = h.get("round")
            fb = html.escape(h.get("feedback") or "")
            ranks = ", ".join(
                f"#{r.get('slot')}={r.get('rank')}"
                for r in sorted(h.get("rankings") or [], key=lambda x: x.get("rank") or 99)
            )
            rows.append(f"<li>Round {rnd}: {html.escape(ranks)} — {fb or '<em>no note</em>'}</li>")
        history_html = f"""
        <details class="collapsible-section">
          <summary>Prototype history ({len(history)} turns)</summary>
          <ul class="feedback-log">{''.join(rows)}</ul>
        </details>
        """

    extra_css = review_css() + """
    .prototype-intro { max-width: 36rem; }
    .round-badge { font-size: 1.1rem; margin-bottom: 0.5rem; }
    .prototype-grid { grid-template-columns: 1fr; }
    @media (min-width: 900px) { .prototype-grid { grid-template-columns: repeat(3, 1fr); } }
    .prototype-card { background: var(--surface); border-radius: 12px; padding: 1rem; }
    .tag-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.5rem 0; }
    .tag-chip { font-size: 0.75rem; background: var(--surface-2); padding: 0.15rem 0.45rem; border-radius: 999px; }
    .tag-chip.wild { background: #fef3c7; color: #92400e; }
    .prototype-card select { width: 100%; min-height: var(--tap-min); margin: 0.5rem 0; }
    .winner-pick { display: block; margin: 0.5rem 0; }
    .feedback-block textarea { width: 100%; margin-top: 0.35rem; }
    .prototype-actions { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 1rem; }
    @media (min-width: 600px) { .prototype-actions { flex-direction: row; flex-wrap: wrap; } }
    .warn-banner { background: var(--warn-bg); color: var(--warn-text); padding: 1rem; border-radius: 8px; }
    .small { font-size: 0.85rem; }
    """

    nav = site_nav(active="prototype", back_href=review_page_path(gig_id), back_label="Review")
    return (
        page_head(f"Prototype — {band}", extra_css=extra_css)
        + nav
        + f"""
  <main class="page-main">
    <h1>Prototype flyers</h1>
    <p class="gig-line"><strong>{short_date}</strong> @ <strong>{venue}</strong></p>
    {body}
    {history_html}
  </main>
"""
        + page_close()
    )


def render_prototype_generating_page(gig_id: str, event: dict[str, Any]) -> str:
    from bridge.review import render_job_progress_page

    return render_job_progress_page(
        gig_id,
        event,
        heading="Generating prototype batch…",
        subtitle="Building 3 directions for you to rank.",
        back_href=prototype_page_path(gig_id),
        back_label="Prototype",
        redirect_href=prototype_page_path(gig_id),
        nav_current="prototype",
    )
