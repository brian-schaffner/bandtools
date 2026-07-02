"""Web UI for two-pass shell design studio."""

from __future__ import annotations

import html
from typing import Any, Optional

from bridge.review import asset_url, pick_page_path, route_path
from bridge.shell_runner import VENUE_TYPES, demo_event_for_venue_type, load_job_summary
from shell_asset_policy import asset_mode_label, final_route_label
from bridge.ui import page_close, page_head, progress_css, review_css, site_nav
from gig_calendar import get_future_gigs, get_local_today
from shell_references import ShellReference, all_shells, get_shell
from state import get_gig_state

from bridge.job_status import get_job_status


def shell_studio_path() -> str:
    return route_path("/shell")


def shell_detail_path(shell_id: str) -> str:
    return route_path(f"/shell/{shell_id}")


def shell_ref_url(shell_id: str) -> str:
    return route_path(f"/shell/ref/{shell_id}")


def shell_run_action(shell_id: str) -> str:
    return route_path(f"/shell/{shell_id}/run")


def shell_job_path(job_id: str) -> str:
    return route_path(f"/shell/job/{job_id}")


def shell_job_status_path(job_id: str) -> str:
    return route_path(f"/shell/job/{job_id}/status")


def shell_job_status_stream_path(job_id: str) -> str:
    return route_path(f"/shell/job/{job_id}/status/stream")


def shell_job_route_action(job_id: str) -> str:
    return route_path(f"/shell/job/{job_id}/route")


def shell_job_final_path(job_id: str) -> str:
    return route_path(f"/shell/job/{job_id}/final")


def _shell_css() -> str:
    return review_css() + """
    .shell-filters {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      margin-bottom: 1.25rem;
    }
    .shell-filters label { font-size: 0.9rem; color: var(--muted); }
    .shell-filters select {
      min-height: var(--tap-min);
      padding: 0.35rem 0.65rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--surface);
      font-size: 1rem;
    }
    .shell-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    }
    .shell-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      text-decoration: none;
      color: inherit;
      transition: box-shadow 0.15s, transform 0.15s;
    }
    .shell-card:hover {
      text-decoration: none;
      box-shadow: 0 4px 14px rgba(0,0,0,0.08);
      transform: translateY(-2px);
    }
    .shell-thumb-wrap {
      aspect-ratio: 2/3;
      background: var(--surface-2);
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }
    .shell-thumb-wrap img { width: 100%; height: 100%; object-fit: cover; }
    .shell-thumb-missing {
      color: var(--muted);
      font-size: 0.85rem;
      padding: 1rem;
      text-align: center;
    }
    .shell-card-body { padding: 0.85rem 1rem 1rem; flex: 1; }
    .shell-card-body h3 {
      font-size: 0.95rem;
      margin: 0 0 0.35rem;
      line-height: 1.3;
    }
    .shell-meta { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.5rem; }
    .shell-chips { display: flex; flex-wrap: wrap; gap: 0.3rem; }
    .shell-chip {
      font-size: 0.7rem;
      background: var(--surface-2);
      border: 1px solid var(--border);
      padding: 0.1rem 0.4rem;
      border-radius: 999px;
      color: var(--muted);
    }
    .shell-detail-layout {
      display: grid;
      gap: 1.5rem;
    }
    @media (min-width: 800px) {
      .shell-detail-layout { grid-template-columns: minmax(200px, 280px) 1fr; }
    }
    .shell-detail-ref {
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      background: var(--surface);
    }
    .shell-detail-ref img { width: 100%; display: block; }
    .shell-form label {
      display: block;
      font-weight: 600;
      margin: 0.75rem 0 0.25rem;
      font-size: 0.95rem;
    }
    .shell-form select, .shell-form input[type="checkbox"] {
      margin-top: 0.25rem;
    }
    .shell-form .checkbox-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin: 1rem 0;
    }
    .shell-form .checkbox-row label { margin: 0; font-weight: 500; }
    .shell-results-grid {
      display: grid;
      gap: 1rem;
    }
    @media (min-width: 720px) {
      .shell-results-grid.cols-2 { grid-template-columns: 1fr 1fr; }
      .shell-results-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
    }
    .shell-result-panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 0.75rem;
    }
    .shell-result-panel h3 { font-size: 0.95rem; margin-bottom: 0.5rem; }
    .shell-result-panel img {
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .eval-wide img { max-width: 100%; }
    .layout-rules { font-size: 0.9rem; color: var(--muted); padding-left: 1.1rem; }
    .palette-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.5rem 0; }
    .palette-swatch {
      width: 1.75rem;
      height: 1.75rem;
      border-radius: 4px;
      border: 1px solid var(--border);
    }
    .shell-review-layout {
      display: grid;
      gap: 1.25rem;
    }
    @media (min-width: 800px) {
      .shell-review-layout { grid-template-columns: 1fr 1fr; }
    }
    .shell-review-mockup img {
      width: 100%;
      border-radius: 12px;
      border: 2px solid var(--accent);
    }
    .shell-route-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.15rem;
      margin-bottom: 0.75rem;
    }
    .shell-route-card.recommended { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(99,102,241,0.12); }
    .shell-route-card h3 { margin: 0 0 0.35rem; font-size: 1rem; }
    .shell-route-card p { margin: 0 0 0.75rem; font-size: 0.9rem; color: var(--muted); }
    .shell-route-badge {
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--accent);
      background: #eef2ff;
      padding: 0.15rem 0.5rem;
      border-radius: 999px;
      margin-bottom: 0.5rem;
    }
    .shell-compare-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      margin-bottom: 1rem;
    }
    """


def _venue_type_options(selected: str = "") -> str:
    opts = ['<option value="">All venue types</option>']
    for vt in VENUE_TYPES:
        sel = ' selected="selected"' if vt == selected else ""
        label = vt.replace("_", " ").title()
        opts.append(f'<option value="{html.escape(vt)}"{sel}>{html.escape(label)}</option>')
    return "".join(opts)


def _shell_card(shell: ShellReference) -> str:
    href = html.escape(shell_detail_path(shell.id))
    title = html.escape(shell.title[:72])
    era = html.escape(shell.era)
    family = html.escape(shell.design_family.replace("_", " "))
    chips = "".join(
        f'<span class="shell-chip">{html.escape(vt.replace("_", " "))}</span>'
        for vt in shell.venue_types[:3]
    )
    if shell.has_image():
        thumb = (
            f'<img src="{html.escape(shell_ref_url(shell.id))}" '
            f'alt="{title}" loading="lazy" />'
        )
    else:
        thumb = '<div class="shell-thumb-missing">Reference image not cached</div>'
    return f"""
    <a class="shell-card" href="{href}">
      <div class="shell-thumb-wrap">{thumb}</div>
      <div class="shell-card-body">
        <h3>{title}</h3>
        <p class="shell-meta">{era} · {family}</p>
        <div class="shell-chips">{chips or '<span class="shell-chip">general</span>'}</div>
      </div>
    </a>
    """


def render_shell_studio_page(*, venue_filter: str = "") -> str:
    shells = all_shells()
    if venue_filter:
        shells = [s for s in shells if venue_filter in s.venue_types]
    with_images = sum(1 for s in all_shells() if s.has_image())
    cards = "".join(_shell_card(s) for s in shells) or '<p class="muted">No shells match that filter.</p>'

    filter_form = f"""
    <form class="shell-filters" method="get" action="{html.escape(shell_studio_path())}">
      <label>Venue type
        <select name="venue_type" onchange="this.form.submit()">
          {_venue_type_options(venue_filter)}
        </select>
      </label>
      {f'<a class="btn btn-secondary" href="{html.escape(shell_studio_path())}">Clear filter</a>' if venue_filter else ''}
    </form>
    """

    return (
        page_head("Shell Design Studio", extra_css=_shell_css())
        + site_nav(active="shell", back_href=pick_page_path(), back_label="Pick gig")
        + f"""
  <main class="page-main">
    <h1>Shell Design Studio</h1>
    <p class="lead">Two-pass AI flyer design — pick a reference poster shell, generate a placeholder design (pass 1), then personalize with your gig, band photo, and logo (pass 2).</p>
    <p class="muted">{len(all_shells())} shells · {with_images} with cached reference images</p>
    {filter_form}
    <div class="shell-grid">{cards}</div>
  </main>
"""
        + page_close()
    )


def _gig_select_options(selected_gig_id: str = "", demo_mode: bool = False) -> str:
    gigs = get_future_gigs(min_days=0, max_days=90, background_refresh=True)
    opts = []
    if demo_mode or not selected_gig_id:
        opts.append('<option value="">— Demo gig (by venue type) —</option>')
    for event in gigs:
        record = get_gig_state(event.gig_id) or {}
        label = f"{event.event_date.strftime('%b %d')} — {event.venue}"
        sel = ' selected="selected"' if event.gig_id == selected_gig_id else ""
        opts.append(f'<option value="{html.escape(event.gig_id)}"{sel}>{html.escape(label)}</option>')
    return "".join(opts)


def render_shell_detail_page(shell_id: str) -> str:
    shell = get_shell(shell_id)
    if shell is None:
        return (
            page_head("Shell not found", extra_css=_shell_css())
            + site_nav(active="shell", back_href=shell_studio_path(), back_label="All shells")
            + f"""
  <main class="page-main">
    <h1>Shell not found</h1>
    <p>Unknown shell id: <code>{html.escape(shell_id)}</code></p>
    <p><a class="btn" href="{html.escape(shell_studio_path())}">Browse shells</a></p>
  </main>
"""
            + page_close()
        )

    title = html.escape(shell.title)
    ref_html = (
        f'<img src="{html.escape(shell_ref_url(shell.id))}" alt="{title}" />'
        if shell.has_image()
        else '<p class="muted">Reference image not cached — pass 1 may be weaker.</p>'
    )
    rules = "".join(f"<li>{html.escape(r)}</li>" for r in shell.layout_rules)
    palette = "".join(
        f'<span class="palette-swatch" style="background:{html.escape(c)}" title="{html.escape(c)}"></span>'
        for c in shell.palette
    )
    venue_types = ", ".join(html.escape(vt.replace("_", " ")) for vt in shell.venue_types) or "general"

    return (
        page_head(f"Shell — {shell.design_family}", extra_css=_shell_css())
        + site_nav(active="shell", back_href=shell_studio_path(), back_label="All shells")
        + f"""
  <main class="page-main">
    <h1>{title}</h1>
    <p class="muted">{html.escape(shell.era)} · {html.escape(shell.style.replace("_", " "))} · {venue_types}</p>
    <div class="shell-detail-layout">
      <figure class="shell-detail-ref">{ref_html}</figure>
      <div>
        <section class="panel">
          <h2>Design family</h2>
          <p>{html.escape(shell.design_family.replace("_", " "))}</p>
          <p class="muted">{html.escape(shell.venue_context.replace("_", " "))}</p>
          <h3>Palette</h3>
          <div class="palette-row">{palette}</div>
          <h3>Layout rules</h3>
          <ul class="layout-rules">{rules}</ul>
        </section>
        <section class="panel shell-form">
          <h2>Generate</h2>
          <form method="post" action="{html.escape(shell_run_action(shell.id))}">
            <label for="gig_id">Gig (calendar)</label>
            <select name="gig_id" id="gig_id">
              {_gig_select_options()}
            </select>
            <label for="venue_type">Or demo gig by venue type</label>
            <select name="venue_type" id="venue_type">
              {_venue_type_options(shell.venue_types[0] if shell.venue_types else "regional_club")}
            </select>
            <p class="muted">Leave gig blank to use the demo event for the venue type above.</p>
            <div class="checkbox-row">
              <input type="checkbox" name="pass1_only" id="pass1_only" value="1" />
              <label for="pass1_only">Pass 1 only (design shell with placeholders — no gig mockup)</label>
            </div>
            <div class="checkbox-row">
              <input type="checkbox" name="skip_mockup" id="skip_mockup" value="1" />
              <label for="skip_mockup">Skip mockup review (use suggested route automatically)</label>
            </div>
            <button type="submit" class="btn btn-purple btn-block">Start shell design</button>
          </form>
        </section>
      </div>
    </div>
  </main>
"""
        + page_close()
    )


def render_shell_generating_page(
    job_id: str,
    *,
    shell_title: str,
    detail: str = "",
    pass1_only: bool = False,
    final_only: bool = False,
    venue: str = "",
) -> str:
    """Progress UI for shell design jobs (full pipeline or final pass only)."""
    status_url = html.escape(shell_job_status_path(job_id))
    stream_url = html.escape(shell_job_status_stream_path(job_id))
    results_url = html.escape(shell_job_path(job_id))
    studio = html.escape(shell_studio_path())
    heading = "Shell design in progress"
    subtitle = html.escape(shell_title[:80])
    venue_line = ""
    if venue:
        venue_line = f'<p class="gig-line">Gig: <strong>{html.escape(venue)}</strong></p>'
    detail_html = f'<p class="muted"><em>{html.escape(detail)}</em></p>' if detail else ""
    pass1_only_js = "true" if pass1_only else "false"
    final_only_js = "true" if final_only else "false"

    extra_css = progress_css() + """
    .shell-progress-card { max-width: 42rem; }
    .shell-overall-bar {
      height: 10px;
      border-radius: 999px;
      background: var(--surface-2);
      border: 1px solid var(--border);
      overflow: hidden;
      margin: 0.75rem 0 1.25rem;
    }
    .shell-overall-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #818cf8, #6366f1);
      transition: width 0.4s ease-out;
    }
    .shell-steps { display: grid; gap: 0.85rem; margin: 1rem 0; }
    .shell-step {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 0.85rem 1rem;
      background: var(--surface-2);
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 0.75rem 1rem;
      align-items: start;
    }
    .shell-step.active { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(99,102,241,0.15); background: var(--surface); }
    .shell-step.done { border-color: var(--green); }
    .shell-step.error { border-color: #ef4444; }
    .shell-step.skipped { opacity: 0.55; }
    .shell-step-badge {
      width: 2rem; height: 2rem; border-radius: 999px;
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 0.95rem;
      background: var(--bg); border: 1px solid var(--border); color: var(--muted);
    }
    .shell-step.active .shell-step-badge { background: #eef2ff; color: var(--accent); border-color: var(--accent); }
    .shell-step.done .shell-step-badge { background: var(--pass-bg); color: var(--green); border-color: var(--green); }
    .shell-step.error .shell-step-badge { background: #fef2f2; color: #ef4444; border-color: #ef4444; }
    .shell-step-body h3 { margin: 0 0 0.2rem; font-size: 1rem; }
    .shell-step-body p { margin: 0; font-size: 0.9rem; color: var(--muted); }
    .shell-step-phase { font-size: 0.85rem; font-weight: 600; margin-top: 0.35rem; color: var(--accent); }
    .shell-step.done .shell-step-phase { color: var(--green); }
    .shell-step.error .shell-step-phase { color: #ef4444; }
    .shell-step-bar {
      grid-column: 1 / -1;
      height: 6px;
      border-radius: 999px;
      background: #e8f5e0;
      overflow: hidden;
      margin-top: 0.15rem;
    }
    .shell-step-bar-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #818cf8, #6366f1);
      transition: width 0.35s ease-out;
    }
    .shell-step.done .shell-step-bar-fill { background: var(--green); width: 100% !important; }
    .shell-meta-row {
      display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem;
      font-size: 0.9rem; color: var(--muted); margin: 0.5rem 0 0;
    }
    .shell-meta-row strong { color: var(--text); }
    """

    step1_extra = ' class="shell-step done" id="step-pass1"' if final_only else ' class="shell-step" id="step-pass1"'
    step_prepass_extra = ' class="shell-step skipped" id="step-prepass"' if pass1_only else ' class="shell-step" id="step-prepass"'
    if final_only:
        step_prepass_extra = ' class="shell-step done" id="step-prepass"'
    step2_extra = ' class="shell-step skipped" id="step-pass2"' if pass1_only else ' class="shell-step" id="step-pass2"'
    step3_extra = ' class="shell-step skipped" id="step-eval"' if pass1_only else ' class="shell-step" id="step-eval"'
    if final_only:
        step2_extra = ' class="shell-step" id="step-pass2"'
        step3_extra = ' class="shell-step" id="step-eval"'

    return (
        page_head(heading, extra_css=extra_css)
        + site_nav(active="shell", back_href=studio, back_label="Shell studio")
        + f"""
  <main class="page-main">
  <div class="progress-card shell-progress-card">
    <h1>{html.escape(heading)}</h1>
    <p class="gig-line"><strong>{subtitle}</strong></p>
    {venue_line}
    {detail_html}
    <p class="overall-status" id="overall-status">Starting…</p>
    <div class="shell-overall-bar" aria-hidden="true"><div class="shell-overall-fill" id="overall-fill"></div></div>
    <div class="shell-meta-row">
      <span>Elapsed: <strong id="elapsed">0:00</strong></span>
      <span id="eta-wrap">Est. step: <strong id="eta">~90s</strong></span>
    </div>

    <div class="shell-steps">
      <article{step1_extra} data-step="pass1">
        <div class="shell-step-badge" id="badge-pass1">{"✓" if final_only else "1"}</div>
        <div class="shell-step-body">
          <h3>Pass 1 — Design shell</h3>
          <p>Match the reference style with placeholder text only (HEADLINER, VENUE, DATE…)</p>
          <div class="shell-step-phase" id="phase-pass1">{"Complete" if final_only else "Waiting"}</div>
        </div>
        <div class="shell-step-bar"><div class="shell-step-bar-fill" id="fill-pass1"{" style=\"width:100%\"" if final_only else ""}></div></div>
      </article>

      <article{step_prepass_extra} data-step="prepass">
        <div class="shell-step-badge" id="badge-prepass">{"✓" if final_only else "2"}</div>
        <div class="shell-step-body">
          <h3>Pre-pass — Text mockup</h3>
          <p>Fast preview with your gig details — no photo or logo</p>
          <div class="shell-step-phase" id="phase-prepass">{"Complete" if final_only else ("Skipped" if pass1_only else "Waiting")}</div>
        </div>
        <div class="shell-step-bar"><div class="shell-step-bar-fill" id="fill-prepass"{" style=\"width:100%\"" if final_only else ""}></div></div>
      </article>

      <article{step2_extra} data-step="pass2">
        <div class="shell-step-badge" id="badge-pass2">{"3" if not pass1_only else "2"}</div>
        <div class="shell-step-body">
          <h3>Final pass — Personalize</h3>
          <p>High-quality flyer after you choose text-only or photo &amp; logo</p>
          <div class="shell-step-phase" id="phase-pass2">{"Skipped" if pass1_only else "Waiting"}</div>
        </div>
        <div class="shell-step-bar"><div class="shell-step-bar-fill" id="fill-pass2"></div></div>
      </article>

      <article{step3_extra} data-step="eval">
        <div class="shell-step-badge" id="badge-eval3">{"4" if not pass1_only else "3"}</div>
        <div class="shell-step-body">
          <h3>Evaluation card</h3>
          <p>Side-by-side: reference · shell · personalized flyer</p>
          <div class="shell-step-phase" id="phase-eval">{"Skipped" if pass1_only else "Waiting"}</div>
        </div>
        <div class="shell-step-bar"><div class="shell-step-bar-fill" id="fill-eval"></div></div>
      </article>
    </div>

    <div class="log-panel" id="log-panel" aria-live="polite"></div>
    <p class="muted" id="status-hint">OpenAI image edits usually take 1–2 minutes per pass.</p>
  </div>
  </main>
  <script>
    const statusUrl = "{status_url}";
    const streamUrl = "{stream_url}";
    const resultsUrl = "{results_url}";
    const pass1Only = {pass1_only_js};
    const finalOnly = {final_only_js};
    const STEP_ORDER = pass1Only ? ["pass1"] : ["pass1", "prepass", "pass2", "eval"];
    const STEP_EST = {{ pass1: 75, prepass: 60, pass2: 90, eval: 8 }};
    let lastLogRevision = -1;
    let startedAt = Date.now();
    let stepStartedAt = Date.now();
    let currentStep = finalOnly ? "pass2" : "";
    let finished = false;

    if (finalOnly) {{
      currentStep = "pass2";
      stepStartedAt = Date.now();
    }}

    function fmtElapsed(ms) {{
      const s = Math.floor(ms / 1000);
      const m = Math.floor(s / 60);
      return m + ":" + String(s % 60).padStart(2, "0");
    }}

    function stepState(step, substep, jobStatus) {{
      if (jobStatus === "error") {{
        if (step === currentStep) return "error";
        const ci = STEP_ORDER.indexOf(currentStep);
        const si = STEP_ORDER.indexOf(step);
        if (si < ci) return "done";
        return "pending";
      }}
      if (jobStatus === "awaiting_route") {{
        if (step === "prepass") return "done";
        if (step === "pass1") return "done";
        return "pending";
      }}
      if (jobStatus === "done") return pass1Only && step !== "pass1" ? "skipped" : "done";
      const activeIdx = STEP_ORDER.indexOf(currentStep);
      const idx = STEP_ORDER.indexOf(step);
      if (substep === "saved") return "done";
      if (step === currentStep) return "active";
      if (idx >= 0 && activeIdx >= 0 && idx < activeIdx) return "done";
      if (pass1Only && step !== "pass1") return "skipped";
      return "pending";
    }}

    function stepFillPct(step, substep, elapsedSec) {{
      if (substep === "saved") return 100;
      const est = STEP_EST[step] || 60;
      if (substep === "briefing" || substep === "canvas" || substep === "start") return Math.min(35, 10 + elapsedSec * 8);
      if (substep === "api") return Math.min(92, 18 + (elapsedSec / est) * 74);
      return Math.min(90, (elapsedSec / est) * 90);
    }}

    function applyStatus(data) {{
      const status = data.status || "idle";
      const msg = data.message || "";
      const step = data.step || "";
      const substep = data.substep || "";
      const progress = Math.min(100, Math.max(0, parseInt(data.progress || 0, 10)));

      if (step && step !== currentStep) {{
        currentStep = step;
        stepStartedAt = Date.now();
      }}

      document.getElementById("overall-status").textContent = msg || status;
      document.getElementById("overall-fill").style.width = progress + "%";
      document.getElementById("elapsed").textContent = fmtElapsed(Date.now() - startedAt);

      const activeEst = STEP_EST[currentStep] || 90;
      const stepElapsed = (Date.now() - stepStartedAt) / 1000;
      const remaining = Math.max(0, Math.ceil(activeEst - stepElapsed));
      document.getElementById("eta").textContent = status === "running" ? ("~" + remaining + "s") : "—";

      ["pass1", "prepass", "pass2", "eval"].forEach((s) => {{
        const el = document.getElementById("step-" + s);
        const phase = document.getElementById("phase-" + s);
        const fill = document.getElementById("fill-" + s);
        const badgeId = s === "eval" ? "eval3" : s;
        const badge = document.getElementById("badge-" + badgeId);
        if (!el || !phase || !fill) return;
        const st = stepState(s, s === step ? substep : (STEP_ORDER.indexOf(s) < STEP_ORDER.indexOf(currentStep) ? "saved" : ""), status);
        el.classList.remove("active", "done", "error", "skipped");
        el.classList.add(st);
        if (st === "done") {{
          phase.textContent = "Complete";
          fill.style.width = "100%";
          if (badge) badge.textContent = "✓";
        }} else if (st === "error") {{
          phase.textContent = data.error || "Failed";
          if (badge) badge.textContent = "!";
        }} else if (st === "skipped") {{
          phase.textContent = "Skipped";
          fill.style.width = "0%";
        }} else if (st === "active") {{
          phase.textContent = msg || substep || "Working…";
          const pct = stepFillPct(s, substep, stepElapsed);
          fill.style.width = pct + "%";
        }} else {{
          phase.textContent = "Waiting";
          fill.style.width = "0%";
        }}
      }});

      if (data.log_revision !== lastLogRevision && Array.isArray(data.log)) {{
        lastLogRevision = data.log_revision;
        const panel = document.getElementById("log-panel");
        panel.innerHTML = data.log.map(e => '<div class="log-line">' + (e.text || '') + '</div>').join('');
        panel.scrollTop = panel.scrollHeight;
      }}

      if (status === "awaiting_route" && !finished) {{
        finished = true;
        document.getElementById("status-hint").textContent = "Mockup ready — choose text-only or photo & logo…";
        setTimeout(() => {{ window.location.href = resultsUrl; }}, 600);
      }}
      if (status === "done" && !finished) {{
        finished = true;
        document.getElementById("status-hint").textContent = "Done — opening results…";
        setTimeout(() => {{ window.location.href = resultsUrl; }}, 600);
      }}
      if (status === "error") {{
        document.getElementById("overall-status").className = "overall-status error";
        document.getElementById("status-hint").textContent = data.error || msg || "Something went wrong.";
      }}
    }}

    function tickClock() {{
      if (finished) return;
      document.getElementById("elapsed").textContent = fmtElapsed(Date.now() - startedAt);
      if (currentStep) {{
        const stepElapsed = (Date.now() - stepStartedAt) / 1000;
        const fill = document.getElementById("fill-" + currentStep);
        const phase = document.getElementById("phase-" + currentStep);
        const el = document.getElementById("step-" + currentStep);
        if (fill && el && el.classList.contains("active")) {{
          const sub = "api";
          fill.style.width = stepFillPct(currentStep, sub, stepElapsed) + "%";
        }}
      }}
    }}
    setInterval(tickClock, 500);

    if (typeof EventSource !== "undefined") {{
      const es = new EventSource(streamUrl);
      es.onmessage = (ev) => {{
        try {{ applyStatus(JSON.parse(ev.data)); }} catch (e) {{}}
      }};
      es.onerror = () => {{ /* polling fallback below */ }};
      setInterval(async () => {{
        if (finished) return;
        try {{
          const r = await fetch(statusUrl);
          applyStatus(await r.json());
        }} catch (e) {{}}
      }}, 2000);
    }} else {{
      setInterval(async () => {{
        const r = await fetch(statusUrl);
        applyStatus(await r.json());
      }}, 1200);
    }}
  </script>
"""
        + page_close()
    )


def render_shell_review_page(job_id: str, summary: dict[str, Any]) -> str:
    """Mockup review — user chooses text-only final vs photo/logo final."""
    shell_title = html.escape(summary.get("shell_title") or "")
    shell_id = summary.get("shell_id") or ""
    pass1 = summary.get("pass1") or {}
    prepass = summary.get("prepass") or {}
    route_info = summary.get("route") or {}
    event = summary.get("event") or {}
    suggested = route_info.get("suggested") or prepass.get("suggested_route") or "text_only"

    venue_line = ""
    if event.get("venue"):
        venue_line = (
            f'<p class="gig-line"><strong>{html.escape(event.get("short_date") or event.get("date", ""))}</strong>'
            f' @ <strong>{html.escape(event.get("venue", ""))}</strong></p>'
        )

    compare_panels: list[str] = []
    if pass1.get("shell_rel"):
        compare_panels.append(
            _result_panel("Pass 1 — placeholders", pass1["shell_rel"], "Design shell")
        )
    if prepass.get("mockup_rel"):
        compare_panels.append(
            _result_panel("Pre-pass mockup", prepass["mockup_rel"], "Text-only preview — not final quality")
        )

    shell = get_shell(shell_id) if shell_id else None
    suggested_label = final_route_label(suggested)
    if shell is not None:
        mode = "typography_only" if suggested == "text_only" else "photo_inset"
        hint = asset_mode_label(mode)
    else:
        hint = suggested_label

    text_only_rec = ' recommended' if suggested == "text_only" else ""
    photo_rec = ' recommended' if suggested == "photo_logo" else ""
    text_badge = '<span class="shell-route-badge">Suggested</span>' if suggested == "text_only" else ""
    photo_badge = '<span class="shell-route-badge">Suggested</span>' if suggested == "photo_logo" else ""
    route_url = html.escape(shell_job_route_action(job_id))
    studio = html.escape(shell_studio_path())
    browse = html.escape(shell_detail_path(shell_id)) if shell_id else studio

    return (
        page_head("Review mockup", extra_css=_shell_css())
        + site_nav(active="shell", back_href=studio, back_label="All shells")
        + f"""
  <main class="page-main">
    <h1>Pre-pass mockup</h1>
    <p class="muted">{shell_title}</p>
    {venue_line}
    <p>Does this shell work well with your gig details as <strong>text only</strong> (no photo or logo)?
       If yes, finalize typography-only. If not, try photo &amp; logo — or pick another shell.</p>
    <p class="muted">System suggestion: <strong>{html.escape(hint)}</strong></p>

    <div class="shell-compare-grid">{''.join(compare_panels)}</div>

    <section class="panel">
      <h2>Choose final path</h2>
      <form method="post" action="{route_url}">
        <div class="shell-route-card{text_only_rec}">
          {text_badge}
          <h3>Finalize text-only</h3>
          <p>High-quality typography pass — no band photo, no logo overlay.</p>
          <button type="submit" name="route" value="text_only" class="btn btn-purple">Text-only final</button>
        </div>
        <div class="shell-route-card{photo_rec}">
          {photo_badge}
          <h3>Add photo &amp; logo</h3>
          <p>Style and lock band photo and logo into the shell layout.</p>
          <button type="submit" name="route" value="photo_logo" class="btn btn-secondary">Photo &amp; logo final</button>
        </div>
      </form>
      <p class="btn-row" style="margin-top:1rem">
        <a class="btn btn-secondary" href="{browse}">Try another shell</a>
        <a class="btn btn-secondary" href="{studio}">Browse all shells</a>
      </p>
    </section>
  </main>
"""
        + page_close()
    )


def render_shell_results_page(job_id: str) -> str:
    summary = load_job_summary(job_id)
    job = get_job_status(job_id)
    if not summary and job.get("status") == "running":
        shell_title = job.get("title") or "Shell design"
        pass1_only = "Pass 1 only" in (job.get("detail") or "")
        venue = ""
        if " · " in (job.get("detail") or ""):
            venue = job.get("detail", "").split(" · ", 1)[0]
        return render_shell_generating_page(
            job_id,
            shell_title=shell_title,
            detail=job.get("detail") or "",
            pass1_only=pass1_only,
            venue=venue,
        )

    if not summary:
        return (
            page_head("Shell job", extra_css=_shell_css())
            + site_nav(active="shell", back_href=shell_studio_path(), back_label="All shells")
            + f"""
  <main class="page-main">
    <h1>Job not found</h1>
    <p class="muted">No results for job <code>{html.escape(job_id)}</code></p>
    <p><a class="btn" href="{html.escape(shell_studio_path())}">Browse shells</a></p>
  </main>
"""
            + page_close()
        )

    job_status = job.get("status") or summary.get("status") or ""
    if job_status == "awaiting_route" or summary.get("status") == "awaiting_route":
        return render_shell_review_page(job_id, summary)

    shell_title = html.escape(summary.get("shell_title") or "")
    shell_id = summary.get("shell_id") or ""
    pass1 = summary.get("pass1") or {}
    pass2 = summary.get("pass2") or {}
    pass1_only = bool(summary.get("pass1_only"))
    event = summary.get("event") or {}

    panels: list[str] = []
    if pass1.get("shell_rel"):
        panels.append(
            _result_panel("Pass 1 — design shell", pass1["shell_rel"], "Placeholder text only")
        )
    prepass = summary.get("prepass") or {}
    if prepass.get("mockup_rel"):
        panels.append(
            _result_panel("Pre-pass mockup", prepass["mockup_rel"], "Fast text-only preview")
        )
    if pass2.get("personalized_rel"):
        route = pass2.get("route") or summary.get("route", {}).get("chosen") or ""
        route_cap = final_route_label(route) if route else "Personalized"
        panels.append(
            _result_panel(f"Final — {route_cap}", pass2["personalized_rel"], event.get("venue", ""))
        )
    eval_rel = summary.get("evaluation_rel")
    eval_html = ""
    if eval_rel:
        eval_html = f"""
        <section class="panel eval-wide">
          <h2>Evaluation — reference · shell · personalized</h2>
          <img src="{html.escape(asset_url(eval_rel))}" alt="Shell evaluation card" loading="lazy" />
        </section>
        """

    venue_line = ""
    if event.get("venue"):
        venue_line = f'<p class="gig-line"><strong>{html.escape(event.get("short_date") or event.get("date", ""))}</strong> @ <strong>{html.escape(event.get("venue", ""))}</strong></p>'

    rerun = shell_detail_path(shell_id) if shell_id else shell_studio_path()

    return (
        page_head(f"Results — {summary.get('design_family', 'shell')}", extra_css=_shell_css())
        + site_nav(active="shell", back_href=shell_studio_path(), back_label="All shells")
        + f"""
  <main class="page-main">
    <h1>Shell design results</h1>
    <p class="muted">{shell_title}</p>
    {venue_line}
    <div class="shell-results-grid cols-{min(len(panels), 3) if panels else 1}">{''.join(panels)}</div>
    {eval_html}
    <p class="btn-row" style="margin-top:1.5rem">
      <a class="btn btn-purple" href="{html.escape(rerun)}">Run again</a>
      <a class="btn btn-secondary" href="{html.escape(shell_studio_path())}">Browse shells</a>
    </p>
  </main>
"""
        + page_close()
    )


def _result_panel(label: str, rel_path: str, caption: str) -> str:
    cap = html.escape(caption) if caption else ""
    return f"""
    <figure class="shell-result-panel">
      <h3>{html.escape(label)}</h3>
      {f'<p class="muted">{cap}</p>' if cap else ''}
      <img src="{html.escape(asset_url(rel_path))}" alt="{html.escape(label)}" loading="lazy" />
    </figure>
    """
