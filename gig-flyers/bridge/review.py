"""Review page data and HTML for gig flyer iterations."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from bridge.job_status import get_job_status
from bridge.imessage import imessage_configured
from bridge.ui import page_close, page_head, progress_css, review_css, site_nav
from state import can_regenerate, get_gig_state, load_state

from output_paths import get_output_dir, output_relative, resolve_output_path

OUTPUT_DIR = get_output_dir()


def root_path() -> str:
    """URL path prefix when served behind Tailscale (e.g. /flyers)."""
    explicit = os.getenv("ROOT_PATH", "").strip().rstrip("/")
    if explicit:
        return explicit if explicit.startswith("/") else f"/{explicit}"
    public = os.getenv("BRIDGE_PUBLIC_URL", "").strip()
    if public:
        path = urlparse(public).path.rstrip("/")
        return path if path else ""
    return ""


def route_path(path: str) -> str:
    """Build a browser-facing path including ROOT_PATH /flyers prefix."""
    path = path if path.startswith("/") else f"/{path}"
    prefix = root_path()
    if prefix and not path.startswith(f"{prefix}/"):
        return f"{prefix}{path}"
    return path


def public_base_url() -> str:
    base = os.getenv("BRIDGE_PUBLIC_URL", "").strip().rstrip("/")
    if base:
        return base
    port = os.getenv("BRIDGE_PORT", "8010")
    return f"http://127.0.0.1:{port}"


def asset_url(rel_path: str) -> str:
    path = Path(rel_path)
    if path.is_absolute():
        try:
            rel = output_relative(path)
        except ValueError:
            rel = rel_path.lstrip("/")
    else:
        rel = rel_path.lstrip("/")
    return f"{public_base_url()}/{rel}"


def review_url(gig_id: str) -> str:
    return f"{public_base_url()}/review/{gig_id}"


def approve_action(gig_id: str) -> str:
    return route_path(f"/review/{gig_id}/approve")


def revise_action(gig_id: str) -> str:
    return route_path(f"/review/{gig_id}/revise")


def review_page_path(gig_id: str) -> str:
    return route_path(f"/review/{gig_id}")


def pick_page_path() -> str:
    return route_path("/pick")


def pick_action(gig_id: str) -> str:
    return route_path(f"/pick/{gig_id}/generate")


def pick_regenerate_action(gig_id: str) -> str:
    return route_path(f"/pick/{gig_id}/regenerate")


def regenerate_action(gig_id: str) -> str:
    return route_path(f"/review/{gig_id}/regenerate")


def job_status_path(gig_id: str) -> str:
    return route_path(f"/review/{gig_id}/status")


def job_status_stream_path(gig_id: str) -> str:
    return route_path(f"/review/{gig_id}/status/stream")


def home_page_path() -> str:
    return route_path("/")


def band_tools_home_path() -> str:
    """Band Tools hub (setlist-helper root). Same host uses /; override via BAND_TOOLS_URL."""
    explicit = os.getenv("BAND_TOOLS_URL", "").strip().rstrip("/")
    if explicit:
        return f"{explicit}/"
    return "/"


def setlist_loader_path() -> str:
    """Setlist Loader tool."""
    explicit = os.getenv("BAND_TOOLS_URL", "").strip().rstrip("/")
    if explicit:
        return f"{explicit}/setlist-loader"
    return "/setlist-loader"


def _gig_output_dir(gig_id: str) -> Optional[Path]:
    direct = OUTPUT_DIR / gig_id
    if direct.is_dir():
        return direct
    if not OUTPUT_DIR.exists():
        return None
    date_prefix = gig_id.split("_", 1)[0]
    for path in OUTPUT_DIR.iterdir():
        if path.is_dir() and path.name.startswith(date_prefix):
            return path
    return None


def _is_valid_image(rel: str, min_bytes: int = 1024) -> bool:
    path = resolve_output_path(rel)
    try:
        return path.is_file() and path.stat().st_size >= min_bytes
    except OSError:
        return False


def _filter_valid_options(options: dict[str, str]) -> dict[str, str]:
    return {letter: rel for letter, rel in sorted(options.items()) if _is_valid_image(rel)}


def _scan_rounds(gig_dir: Path) -> list[dict[str, Any]]:
    rounds: dict[int, dict[str, Any]] = {}
    for manifest in sorted(gig_dir.glob("manifest_r*.json")):
        match = re.search(r"manifest_r(\d+)\.json$", manifest.name)
        if not match:
            continue
        round_num = int(match.group(1))
        data = json.loads(manifest.read_text(encoding="utf-8"))
        options = _filter_valid_options(data.get("options", {}))
        if not options:
            continue
        rounds[round_num] = {
            "round": round_num,
            "options": options,
            "event": data.get("event", {}),
        }

    for png in sorted(gig_dir.glob("option-*_r*.png")):
        match = re.search(r"option-([ABCD])_r(\d+)\.png$", png.name)
        if not match:
            continue
        letter, round_num = match.group(1), int(match.group(2))
        rel = output_relative(png)
        if not _is_valid_image(rel):
            continue
        rounds.setdefault(round_num, {"round": round_num, "options": {}, "event": {}})
        rounds[round_num]["options"][letter] = rel

    result: list[dict[str, Any]] = []
    for round_num in sorted(rounds):
        options = _filter_valid_options(rounds[round_num]["options"])
        if not options:
            continue
        rounds[round_num]["options"] = options
        result.append(rounds[round_num])
    return result


def build_review_data(gig_id: str) -> dict[str, Any]:
    record = get_gig_state(gig_id) or {}
    gig_dir = _gig_output_dir(gig_id)
    all_rounds = _scan_rounds(gig_dir) if gig_dir else []
    event = record.get("event") or (all_rounds[-1]["event"] if all_rounds else {})

    state_round = int(record.get("round") or 0)
    latest_scanned = all_rounds[-1]["round"] if all_rounds else 0
    current_round = state_round or latest_scanned

    state_options = _filter_valid_options(record.get("options", {}))
    if state_options and state_round == current_round:
        current_options = state_options
    elif all_rounds:
        current_options = all_rounds[-1]["options"]
        current_round = all_rounds[-1]["round"]
    else:
        current_options = {}

    history_rounds = [r for r in all_rounds if r["round"] < current_round]

    return {
        "gig_id": gig_id,
        "status": record.get("status", "unknown"),
        "event": event,
        "current_round": current_round,
        "current_options": current_options,
        "history_rounds": history_rounds,
        "feedback_history": record.get("feedback_history", []),
        "approved_option": record.get("approved_option"),
        "approved_path": record.get("approved_path"),
        "approval_history": record.get("approval_history", []),
        "research": record.get("research"),
        "selected_photo": record.get("selected_photo"),
        "reviewer_verdicts": record.get("reviewer_verdicts", {}),
        "can_regenerate": can_regenerate(gig_id),
        "review_url": review_url(gig_id),
    }


def build_review_link_message(event: dict[str, Any], gig_id: str, option_count: int) -> str:
    venue = event.get("venue", "Venue TBA")
    short_date = event.get("short_date") or event.get("date", "")
    band = event.get("band", "Lindsey Lane Band")
    link = review_url(gig_id)
    return (
        f"🎸 {band} — {short_date} @ {venue}\n"
        f"{option_count} new flyer options ready for review:\n"
        f"{link}\n\n"
        "Open the link to compare all rounds, approve an option, or request changes."
    )


def _reviewer_note_html(verdict: Optional[dict[str, Any]]) -> str:
    if not verdict:
        return ""
    note = html.escape(str(verdict.get("display_note") or "Passed"))
    css_class = "pass" if verdict.get("pass") else "warn"
    score = verdict.get("score")
    score_html = f' <span class="muted">({score}/10)</span>' if score else ""
    return f'<p class="reviewer-note {css_class}">AI Review: {note}{score_html}</p>'


def public_output_url(path: Path | str) -> str:
    """Browser URL for a generated flyer under /output."""
    p = Path(path)
    if p.is_absolute():
        try:
            rel = output_relative(p)
        except ValueError:
            rel = str(p).replace("\\", "/")
    else:
        rel = str(p).replace("\\", "/")
    if rel.startswith("output/"):
        rel = rel[len("output/") :]
    return route_path(f"/output/{rel}")


def _progress_option_letters() -> tuple[str, ...]:
    from option_slots import round_option_letters

    return round_option_letters()


def _option_progress_card_html(letter: str) -> str:
    esc = html.escape(letter)
    return f"""
      <div class="option-card pending" id="card-{esc}" data-option="{esc}">
        <div class="option-header">
          <span class="option-letter">{esc}</span>
          <span class="engine-badge" id="engine-{esc}"></span>
          <span class="attempt-badge" id="attempt-{esc}"></span>
        </div>
        <div class="phase-label" id="phase-{esc}">Waiting</div>
        <div class="option-preview" id="preview-{esc}">
          <div class="vessel-layer">
            <div class="vessel" aria-label="Option {esc} progress">
              <div class="vessel-fill" id="fill-{esc}"></div>
              <div class="fill-pct" id="pct-{esc}">—</div>
            </div>
          </div>
          <img class="option-thumb" id="thumb-{esc}" alt="Option {esc} preview" />
        </div>
        <div class="option-note" id="note-{esc}"></div>
      </div>"""


def render_job_progress_page(
    gig_id: str,
    event: dict[str, Any],
    *,
    heading: str,
    subtitle: str = "",
    detail: str = "",
    back_href: Optional[str] = None,
    back_label: str = "Back to review",
    redirect_href: Optional[str] = None,
    nav_current: str = "progress",
) -> str:
    """Processing page with per-option vessel progress (SSE + polling fallback)."""
    status_url = html.escape(job_status_path(gig_id))
    stream_url = html.escape(job_status_stream_path(gig_id))
    review = html.escape(redirect_href or review_page_path(gig_id))
    back = back_href or review_page_path(gig_id)
    nav = site_nav(active=nav_current, back_href=back, back_label=back_label)
    venue = html.escape(event.get("venue", "Venue TBA"))
    short_date = html.escape(event.get("short_date") or event.get("date", ""))
    heading_esc = html.escape(heading)
    subtitle_html = f"<p class='muted'>{html.escape(subtitle)}</p>" if subtitle else ""
    detail_html = f'<p class="muted"><em>{html.escape(detail)}</em></p>' if detail else ""
    letters = _progress_option_letters()
    letters_json = json.dumps(list(letters))
    option_cards_html = "".join(_option_progress_card_html(letter) for letter in letters)
    status_hint = (
        "You'll get an iMessage when all options are ready."
        if imessage_configured()
        else "Options will appear on the review page when ready."
    )
    job = get_job_status(gig_id)
    initial_fill_sec = float(job.get("estimated_generate_seconds") or 0)
    if initial_fill_sec <= 0:
        option_estimates = [
            float((job.get("options") or {}).get(letter, {}).get("estimated_generate_seconds") or 0)
            for letter in letters
        ]
        positive = [est for est in option_estimates if est > 0]
        if positive:
            initial_fill_sec = max(positive)
    if initial_fill_sec <= 0:
        initial_fill_sec = 45.0

    return (
        page_head(heading, extra_css=progress_css())
        + nav
        + f"""
  <main class="page-main">
  <div class="progress-card">
    <h1>{heading_esc}</h1>
    <p class="gig-line"><strong>{short_date}</strong> @ <strong>{venue}</strong></p>
    {subtitle_html}
    {detail_html}
    <p class="overall-status" id="overall-status">Starting…</p>
    <p class="provider-badge" id="provider-label" style="display:none"></p>
    <p class="overall-detail" id="overall-detail"></p>

    <div class="options-grid" id="options-grid">
{option_cards_html}
    </div>

    <div class="log-panel" id="log-panel" aria-live="polite"></div>
    <p class="muted" id="status-hint">{html.escape(status_hint)}</p>
  </div>
  </main>
  <script>
    const statusUrl = "{status_url}";
    const streamUrl = "{stream_url}";
    const reviewUrl = "{review}";
    const pollMs = 1000;
    const LETTERS = {letters_json};
    let lastLogRevision = -1;
    let lastOptionsRevision = -1;
    let lastActiveOption = "";
    let eventSource = null;
    let pollTimer = null;
    let finished = false;
    let fillDurationSec = {initial_fill_sec};
    const optionUiState = {{}};
    const fillState = {{}};

    const PHASE_LABELS = {{
      pending: "Waiting",
      generating: "Creating image…",
      reviewing: "AI review…",
      passed: "Complete",
      failed: "Needs remake",
      remaking: "Remaking…",
      error: "Failed",
    }};

    function transitionKey(phase, attempt, exhausted) {{
      return phase + ":" + (attempt || 0) + ":" + (exhausted ? "1" : "0");
    }}

    function parseStartedAt(iso) {{
      if (!iso) return null;
      const t = Date.parse(iso);
      return Number.isFinite(t) ? t : null;
    }}

    function effectiveEstimate(baseEstimate, elapsedSec) {{
      const base = Math.max(1, baseEstimate || fillDurationSec);
      if (elapsedSec <= base) return base;
      const overdue = elapsedSec - base;
      const stretches = Math.floor(overdue / 5) + 1;
      return base * (1 + 0.1 * stretches);
    }}

    function computeFillRatio(elapsedSec, estimateSec) {{
      const eff = effectiveEstimate(estimateSec, elapsedSec);
      return Math.min(0.95, elapsedSec / eff);
    }}

    function stopFillTracking(letter) {{
      const state = fillState[letter];
      if (state && state.rafId) cancelAnimationFrame(state.rafId);
      delete fillState[letter];
    }}

    function startFillTracking(letter, opt) {{
      const fill = document.getElementById("fill-" + letter);
      const pct = document.getElementById("pct-" + letter);
      if (!fill || !pct) return;

      const phase = opt.phase || "pending";
      if (phase !== "generating" && phase !== "remaking") {{
        stopFillTracking(letter);
        return;
      }}

      const attempt = opt.attempt || 0;
      const trackingKey = phase + ":" + attempt;
      const existing = fillState[letter];
      if (existing && existing.trackingKey === trackingKey && existing.rafId) {{
        return;
      }}

      const resume = existing && existing.trackingKey === trackingKey;
      if (!resume) {{
        stopFillTracking(letter);
      }}

      const estimate = resume
        ? existing.estimate
        : ((typeof opt.estimated_generate_seconds === "number" && opt.estimated_generate_seconds > 0)
          ? opt.estimated_generate_seconds
          : fillDurationSec);
      const startedAt = resume
        ? existing.startedAt
        : (parseStartedAt(opt.generate_started_at) || Date.now());
      const maxProgress = resume ? existing.maxProgress : 0;
      const state = {{
        trackingKey,
        estimate,
        startedAt,
        maxProgress,
        rafId: null,
      }};

      function tick() {{
        const cur = optionUiState[letter];
        if (!cur || (cur.phase !== "generating" && cur.phase !== "remaking")) {{
          stopFillTracking(letter);
          return;
        }}
        const elapsed = (Date.now() - state.startedAt) / 1000;
        const computed = computeFillRatio(elapsed, state.estimate);
        const ratio = Math.max(state.maxProgress, computed);
        state.maxProgress = ratio;
        const heightPct = Math.round(ratio * 100);
        fill.classList.remove("locked-full");
        fill.classList.add("filling");
        fill.style.height = heightPct + "%";
        pct.textContent = heightPct + "%";
        state.rafId = requestAnimationFrame(tick);
      }}

      fillState[letter] = state;
      if (!resume) {{
        fill.style.height = "0%";
      }}
      state.rafId = requestAnimationFrame(tick);
    }}

    function lockFillFull(fill) {{
      fill.classList.remove("filling");
      fill.classList.add("locked-full");
      fill.style.height = "100%";
    }}

    function resetFillEmpty(fill) {{
      fill.classList.remove("filling", "locked-full");
      fill.style.height = "0%";
    }}

    function applyOptionVisual(letter, opt) {{
      const fill = document.getElementById("fill-" + letter);
      const pct = document.getElementById("pct-" + letter);
      const preview = document.getElementById("preview-" + letter);
      const thumb = document.getElementById("thumb-" + letter);
      const card = document.getElementById("card-" + letter);
      if (!fill || !card) return;

      const phase = opt.phase || "pending";
      const attempt = opt.attempt || 0;
      const exhausted = !!opt.exhausted;
      const imageUrl = opt.image_url || "";
      const prev = optionUiState[letter] || {{ phase: "pending", attempt: 0, exhausted: false, imageUrl: "", locked: false }};
      const key = transitionKey(phase, attempt, exhausted);
      const prevKey = transitionKey(prev.phase, prev.attempt, prev.exhausted);
      const imageChanged = imageUrl && imageUrl !== prev.imageUrl;
      const phaseChanged = key !== prevKey;

      if (prev.locked && phase === "passed") return;
      if (!phaseChanged && !imageChanged && phase !== "pending") return;

      card.classList.remove("outline-review", "outline-pass", "outline-fail", "fail-flash");

      if (imageUrl && thumb) {{
        const bust = imageUrl + (imageUrl.includes("?") ? "&" : "?") + "v=" + encodeURIComponent(key);
        if (thumb.src !== bust) thumb.src = bust;
      }}

      if (phase === "generating" || phase === "remaking") {{
        if (preview) preview.classList.remove("show-image");
        startFillTracking(letter, opt);
      }} else if (phase === "reviewing") {{
        stopFillTracking(letter);
        if (preview) preview.classList.add("show-image");
        lockFillFull(fill);
        pct.textContent = "…";
        card.classList.add("outline-review");
      }} else if (phase === "passed") {{
        stopFillTracking(letter);
        if (preview) preview.classList.add("show-image");
        lockFillFull(fill);
        pct.textContent = "✓";
        card.classList.add("outline-pass");
        prev.locked = true;
      }} else if (phase === "failed" || phase === "error") {{
        stopFillTracking(letter);
        if (preview) preview.classList.add("show-image");
        lockFillFull(fill);
        pct.textContent = "✗";
        if (exhausted) {{
          card.classList.add("outline-fail");
        }} else {{
          card.classList.add("fail-flash");
          setTimeout(() => {{
            const cur = optionUiState[letter];
            if (cur && cur.phase === "failed" && !cur.exhausted) {{
              document.getElementById("card-" + letter)?.classList.remove("fail-flash");
            }}
          }}, 750);
        }}
      }} else if (phase === "pending") {{
        stopFillTracking(letter);
        if (preview) preview.classList.remove("show-image");
        resetFillEmpty(fill);
        pct.textContent = "—";
        prev.locked = false;
      }}

      optionUiState[letter] = {{
        phase,
        attempt,
        exhausted,
        imageUrl,
        locked: prev.locked || phase === "passed",
      }};
    }}

    function formatTime(iso) {{
      if (!iso) return "";
      try {{
        const d = new Date(iso);
        return d.toLocaleTimeString([], {{ hour: "2-digit", minute: "2-digit", second: "2-digit" }});
      }} catch (e) {{ return ""; }}
    }}

    function renderLog(log, revision) {{
      const panel = document.getElementById("log-panel");
      if (!Array.isArray(log)) return;
      const rev = typeof revision === "number" ? revision : -1;
      if (rev === lastLogRevision && panel.childElementCount > 0) return;
      lastLogRevision = rev;
      panel.replaceChildren();
      const tail = log.slice(-4);
      for (const entry of tail) {{
        const line = document.createElement("div");
        line.className = "log-line";
        line.textContent = (formatTime(entry.at) ? formatTime(entry.at) + " " : "") + (entry.text || "");
        panel.appendChild(line);
      }}
      panel.scrollTop = panel.scrollHeight;
    }}

    function renderOption(letter, opt, activeOption) {{
      const card = document.getElementById("card-" + letter);
      const phaseEl = document.getElementById("phase-" + letter);
      const noteEl = document.getElementById("note-" + letter);
      const attemptEl = document.getElementById("attempt-" + letter);
      const engineEl = document.getElementById("engine-" + letter);
      if (!card || !opt) return;

      const phase = opt.phase || "pending";
      const attempt = opt.attempt || 0;

      card.className = "option-card " + phase;
      if (letter === activeOption && (phase === "generating" || phase === "reviewing" || phase === "remaking")) {{
        card.classList.add("active");
      }}

      if (engineEl) {{
        engineEl.textContent = opt.provider_label || "";
        engineEl.style.display = opt.provider_label ? "" : "none";
      }}

      phaseEl.textContent = PHASE_LABELS[phase] || phase;
      applyOptionVisual(letter, opt);

      if (opt.attempt && opt.attempt > 1) {{
        attemptEl.textContent = "Attempt " + opt.attempt;
        attemptEl.style.display = "";
      }} else {{
        attemptEl.textContent = "";
        attemptEl.style.display = "none";
      }}

      if (phase === "failed" && opt.note) {{
        noteEl.textContent = opt.note;
      }} else if (phase === "error" && opt.note) {{
        noteEl.textContent = opt.note;
      }} else if (phase === "passed") {{
        noteEl.textContent = opt.note || "Passed review";
      }} else if (phase === "reviewing") {{
        noteEl.textContent = "AI reviewer checking…";
      }} else if (phase === "remaking" && opt.note) {{
        noteEl.textContent = opt.note;
      }} else {{
        noteEl.textContent = "";
      }}
    }}

    function renderOptions(options, revision, activeOption) {{
      const rev = typeof revision === "number" ? revision : -1;
      if (rev >= 0 && rev === lastOptionsRevision) {{
        if (activeOption !== lastActiveOption) {{
          for (const letter of LETTERS) {{
            const card = document.getElementById("card-" + letter);
            if (!card) continue;
            card.classList.remove("active");
            if (letter === activeOption) {{
              const phase = (options || {{}})[letter]?.phase;
              if (phase === "generating" || phase === "reviewing" || phase === "remaking") {{
                card.classList.add("active");
              }}
            }}
          }}
          lastActiveOption = activeOption;
        }}
        return;
      }}
      lastOptionsRevision = rev;
      lastActiveOption = activeOption;
      for (const letter of LETTERS) {{
        renderOption(letter, (options || {{}})[letter], activeOption);
      }}
    }}

    function applyStatus(data) {{
      if (finished) return;
      const statusEl = document.getElementById("overall-status");
      const detailEl = document.getElementById("overall-detail");
      const hint = document.getElementById("status-hint");

      if (data.message) statusEl.textContent = data.message;
      detailEl.textContent = data.detail || "";
      const providerEl = document.getElementById("provider-label");
      if (providerEl && data.provider_label) {{
        const label = data.provider_label;
        providerEl.textContent = label.includes(":") ? label : ("Generating with " + label);
        providerEl.style.display = "";
      }}
      if (typeof data.estimated_generate_seconds === "number" && data.estimated_generate_seconds > 0) {{
        fillDurationSec = data.estimated_generate_seconds;
      }} else if (data.options) {{
        const optionEstimates = LETTERS.map((letter) => {{
          const est = data.options[letter] && data.options[letter].estimated_generate_seconds;
          return (typeof est === "number" && est > 0) ? est : 0;
        }}).filter((est) => est > 0);
        if (optionEstimates.length) {{
          fillDurationSec = Math.max(...optionEstimates);
        }}
      }}

      renderOptions(data.options, data.options_revision, data.option || "");
      if (data.log_revision !== lastLogRevision) {{
        renderLog(data.log, data.log_revision);
      }}

      if (data.status === "error") {{
        finished = true;
        if (eventSource) eventSource.close();
        if (pollTimer) clearTimeout(pollTimer);
        statusEl.className = "overall-status error";
        hint.textContent = data.error || "Generation failed.";
        return;
      }}
      if (data.status === "done") {{
        finished = true;
        if (eventSource) eventSource.close();
        if (pollTimer) clearTimeout(pollTimer);
        hint.textContent = "Complete — redirecting to review…";
        window.location.href = reviewUrl;
      }}
    }}

    async function poll() {{
      if (finished) return;
      try {{
        const resp = await fetch(statusUrl + "?_=" + Date.now(), {{ cache: "no-store" }});
        const data = await resp.json();
        applyStatus(data);
      }} catch (err) {{
        document.getElementById("status-hint").textContent = "Status check failed — retrying…";
      }}
      if (!finished) pollTimer = setTimeout(poll, pollMs);
    }}

    function startStream() {{
      if (typeof EventSource !== "undefined") {{
        eventSource = new EventSource(streamUrl);
        eventSource.onmessage = (ev) => {{
          try {{ applyStatus(JSON.parse(ev.data)); }} catch (e) {{ /* ignore */ }}
        }};
        eventSource.onerror = () => {{
          if (eventSource) eventSource.close();
          eventSource = null;
          poll();
        }};
        return;
      }}
      poll();
    }}
    startStream();
  </script>
"""
        + page_close()
    )


def render_regenerating_page(gig_id: str, event: dict[str, Any]) -> str:
    """Shown after regenerate POST while a fresh round is generated."""
    return render_job_progress_page(
        gig_id,
        event,
        heading="Regenerating flyer options…",
        subtitle="Starting a fresh round — new research, photo pick, and 3 new options from scratch.",
    )


def render_processing_page(gig_id: str, option: str, feedback: str) -> str:
    """Shown immediately after revise POST while generation runs in background."""
    record = get_gig_state(gig_id) or {}
    return render_job_progress_page(
        gig_id,
        record.get("event", {}),
        heading="Generating new options…",
        subtitle=f"Revising option {option} with your feedback.",
        detail=feedback,
    )


def render_review_page(data: dict[str, Any]) -> str:
    gig_id = data["gig_id"]
    event = data.get("event", {})
    venue = html.escape(event.get("venue", "Venue TBA"))
    short_date = html.escape(event.get("short_date") or event.get("date", ""))
    band = html.escape(event.get("band", "Lindsey Lane Band"))
    status = html.escape(data.get("status", "unknown"))
    current_round = data.get("current_round", 0)

    current_section = ""
    regenerate_section = ""
    if data.get("can_regenerate"):
        if data.get("status") == "approved":
            confirm_msg = (
                "Start a new round? Previous approval stays in history."
            )
            regen_help = "Generates 3 brand-new options. Your approved flyer is kept in history."
        else:
            confirm_msg = (
                "Start a fresh round? This generates 3 brand-new options from scratch "
                "(not a revision of A/B/C)."
            )
            regen_help = "Fresh research + new layouts — previous rounds stay in history below."
        regenerate_section = f"""
        <div class="sticky-actions">
          <form method="post" action="{html.escape(regenerate_action(gig_id))}"
                onsubmit="return confirm({json.dumps(confirm_msg)});">
            <button type="submit" class="btn btn-purple btn-block regenerate-btn">Regenerate all options</button>
          </form>
          <p class="muted" style="margin:0.5rem 0 0;font-size:0.875rem">{html.escape(regen_help)}</p>
        </div>
        """
    if data.get("status") != "approved" and data.get("current_options"):
        cards = []
        verdicts = data.get("reviewer_verdicts") or {}
        for letter, rel in sorted(data["current_options"].items()):
            img_url = html.escape(asset_url(rel))
            reviewer_html = _reviewer_note_html(verdicts.get(letter))
            cards.append(
                f"""
                <article class="review-option-card" id="option-{letter}">
                  <h3>Option {letter}</h3>
                  {reviewer_html}
                  <img class="flyer-img" src="{img_url}" alt="Option {letter}" loading="lazy" />
                  <div class="option-actions">
                    <form class="approve-form" method="post" action="{html.escape(approve_action(gig_id))}">
                      <input type="hidden" name="option" value="{letter}" />
                      <button type="submit" class="btn btn-green btn-block">Approve {letter}</button>
                    </form>
                    <form class="revise-form" method="post" action="{html.escape(revise_action(gig_id))}">
                      <input type="hidden" name="option" value="{letter}" />
                      <textarea name="feedback" rows="3" placeholder="Feedback for option {letter}…" required></textarea>
                      <button type="submit" class="btn btn-block">Revise {letter}</button>
                    </form>
                  </div>
                </article>
                """
            )
        current_section = f"""
        <section class="current-round">
          <h2>Current options — round {current_round}</h2>
          <div class="options-grid">{''.join(cards)}</div>
        </section>
        """

    history_sections = []
    for rnd in reversed(data.get("history_rounds", [])):
        round_num = rnd["round"]
        imgs = []
        for letter, rel in sorted(rnd.get("options", {}).items()):
            imgs.append(
                f'<figure><figcaption>{letter}</figcaption>'
                f'<img src="{html.escape(asset_url(rel))}" alt="R{round_num} {letter}" loading="lazy" /></figure>'
            )
        history_sections.append(
            f'<details class="history-round"><summary>Round {round_num}</summary>'
            f'<div class="history-grid">{"".join(imgs)}</div></details>'
        )

    history_html = "".join(history_sections) or "<p class='muted'>No prior rounds.</p>"
    history_section = f"""
    <details class="collapsible-section">
      <summary>Iteration history ({len(data.get('history_rounds', []))} rounds)</summary>
      <div class="collapsible-body">{history_html}</div>
    </details>
    """

    feedback_rows = []
    for item in data.get("feedback_history", []):
        feedback_rows.append(
            "<li>"
            f"<strong>{html.escape(item.get('action', ''))} {html.escape(item.get('option', ''))}</strong>"
            f" — {html.escape(item.get('feedback') or item.get('raw_text', ''))}"
            f" <span class='muted'>{html.escape(item.get('at', ''))}</span>"
            "</li>"
        )

    approved_banner = ""
    if data.get("status") == "approved":
        opt = html.escape(str(data.get("approved_option") or ""))
        ap = data.get("approved_path", "")
        thumb_html = ""
        if ap:
            thumb_html = (
                f'<figure class="approved-thumb">'
                f'<img src="{html.escape(asset_url(ap))}" alt="Approved option {opt}" loading="lazy" />'
                f"</figure>"
            )
        approved_banner = f"""
        <div class="approved-banner">
          <div class="approved-row">
            {thumb_html}
            <div>
              <p><strong>Approved option {opt}</strong></p>
              {f'<p><a class="btn btn-green" href="{html.escape(asset_url(ap))}">Download final flyer</a></p>' if ap else ''}
            </div>
          </div>
        </div>
        """

    prior_approvals = ""
    for item in reversed(data.get("approval_history") or []):
        opt = html.escape(str(item.get("option") or ""))
        path = item.get("path") or ""
        rnd = item.get("round", "")
        at = html.escape(str(item.get("at") or ""))
        thumb = ""
        if path:
            thumb = (
                f'<img src="{html.escape(asset_url(path))}" alt="Previously approved {opt}" '
                f'loading="lazy" class="history-approved-thumb" />'
            )
        prior_approvals += (
            f'<li class="prior-approval">Round {rnd} — option {opt} {thumb}'
            f' <span class="muted">{at}</span></li>'
        )
    if prior_approvals:
        approved_banner += f"""
        <details class="collapsible-section">
          <summary>Previous approvals</summary>
          <div class="collapsible-body">
            <ul class="prior-approvals">{prior_approvals}</ul>
          </div>
        </details>
        """

    research_section = ""
    research = data.get("research") or {}
    selected_photo = data.get("selected_photo") or {}
    if research or selected_photo:
        holiday = (research.get("date_context") or {}).get("holiday") or "none"
        demo = ", ".join(research.get("demographics") or [])
        design_notes = research.get("design_notes") or []
        notes_html = "".join(f"<li>{html.escape(n)}</li>" for n in design_notes[:4])
        photo_html = ""
        if selected_photo.get("path"):
            photo_url = html.escape(asset_url(selected_photo["path"]))
            photo_html = f"""
            <figure class="research-photo">
              <img src="{photo_url}" alt="Selected band photo" loading="lazy" />
              <figcaption>{html.escape(selected_photo.get('id', ''))} — {html.escape(selected_photo.get('reason', ''))}</figcaption>
            </figure>
            """
        research_section = f"""
        <details class="collapsible-section">
          <summary>Gig context</summary>
          <div class="collapsible-body">
            <div class="research-grid">
              <div>
                <p><strong>Venue type:</strong> {html.escape(str(research.get('venue_type', 'unknown')))}</p>
                <p><strong>Audience:</strong> {html.escape(demo or 'n/a')}</p>
                <p><strong>Holiday context:</strong> {html.escape(holiday)}</p>
                <p><strong>Design language:</strong> {html.escape(str(research.get('design_language', '')))}</p>
                <ul>{notes_html}</ul>
              </div>
              {photo_html}
            </div>
          </div>
        </details>
        """

    feedback_section = f"""
    <details class="collapsible-section">
      <summary>Feedback log ({len(data.get('feedback_history', []))})</summary>
      <div class="collapsible-body">
        <ul class="feedback-list">{''.join(feedback_rows) or '<li class="muted">No feedback yet.</li>'}</ul>
      </div>
    </details>
    """

    pick = pick_page_path()
    from bridge.prototype import prototype_page_path

    prototype_link = f"""
    <section class="prototype-cta">
      <p><a class="btn btn-purple btn-block" href="{html.escape(prototype_page_path(gig_id))}">
        Rapid prototype mode (3 at a time, rank &amp; iterate)
      </a></p>
      <p class="muted" style="font-size:0.875rem;margin-top:0.35rem">
        Not happy with A/B/C? Try ranking batches of 3 until something clicks or you call it.
      </p>
    </section>
    """
    nav = site_nav(active="review", back_href=pick, back_label="Pick gig")

    return (
        page_head(f"{band} — {short_date}", extra_css=review_css())
        + nav
        + f"""
  <main class="page-main">
  <header class="page-header">
    <h1>{band}</h1>
    <p class="meta">{short_date} @ {venue} · status: {status}</p>
  </header>
  {approved_banner}
  {prototype_link}
  {current_section}
  {regenerate_section}
  {research_section}
  {history_section}
  {feedback_section}
  </main>
"""
        + page_close()
    )
