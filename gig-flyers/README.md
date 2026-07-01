# Gig Flyers

Two-mode flyer system for Lindsey Lane Band: scrape upcoming gigs from [lindseylane.com/dates](https://www.lindseylane.com/dates/), generate 2–3 authentic promoter-style flyer options via OpenAI, send a **review link** via iMessage, and iterate until approved.

## Modes

### Mode 1 — Auto (daily)

Scans the **live calendar** every day for gigs **21–28 days out**. For gigs not yet in `state.json` (or not yet started), generates 3 options and sends an iMessage review link.

```bash
# Manual run (live calendar when GIG_FLYERS_TEST_MODE unset)
python3 scripts/auto_scan.py
python3 flyer_generator.py --auto-scan

# Dry run (no OpenAI, no iMessage)
python3 flyer_generator.py --auto-scan --dry-run

# Daily cron / launchd wrapper
./scripts/daily-auto-scan.sh
```

**Cursor Automation:** import `prompts/automation-daily.json` (cron `0 9 * * *` — daily 9 AM).

Skips gigs that are **approved**, **pending_review**, or already have generated options.

### Mode 2 — Interactive (on demand)

Open the bridge home page, pick any upcoming gig (next 60 days), and trigger generation.

| URL | Purpose |
|-----|---------|
| `https://{machine}.ts.net/flyers/` | Home dashboard (both modes) |
| `https://{machine}.ts.net/flyers/pick` | Interactive gig picker |
| `https://{machine}.ts.net/flyers/review/{gig_id}` | Review / approve / revise |

Local (no Tailscale): `http://127.0.0.1:8010/` and `/pick`.

After you click **Generate 3 options**, you'll see a "generating…" page, get an iMessage when ready, and can open the review page.

## Setup

```bash
cd /Users/brian/dev/gig-flyers
cp .env.example .env
# Edit .env: OPENAI_API_KEY, IMESSAGE_RECIPIENT, BRIDGE_SECRET, BRIDGE_PUBLIC_URL

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Bridge + web review (local Mac)

1. Sign into Messages.app (for link notifications and final delivery)
2. Set `IMESSAGE_RECIPIENT` in `.env` (phone or Apple ID email)
3. Start bridge:

```bash
./scripts/bridge-service.sh
```

4. Expose via Tailscale:

```bash
chmod +x configure-tailscale.sh install-autostart.sh
./configure-tailscale.sh
# Sets BRIDGE_PUBLIC_URL=https://{your-machine}.ts.net/flyers — add to .env
```

5. Open review page for a gig:

```
https://{your-machine}.ts.net/flyers/review/{gig_id}
# Local: http://127.0.0.1:8010/review/{gig_id}
```

### Email on approve

When you approve a flyer on the web page, the final PNG is sent via:

- **Mail.app** (default) — uses `EMAIL_RECIPIENT` or `IMESSAGE_RECIPIENT`; Mail.app must be configured
- **SMTP** (optional) — set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` in `.env`

### iMessage fallback

Text replies (`APPROVE B`, `REVISE B: feedback`) still work if Full Disk Access is granted, but the **primary UX is the web review page**.

### Cursor Automations

Import drafts from:

- `prompts/automation-daily.json` — **daily** 9 AM auto-scan (recommended)
- `prompts/automation-weekly.json` — legacy weekly scan (use daily instead)
- `prompts/automation-iteration.json` — webhook for feedback

Set repo to this project, enable cloud compute, and configure secrets: `OPENAI_API_KEY`, `BRIDGE_PUBLIC_URL`, `BRIDGE_SECRET`.

After saving the iteration automation, copy its webhook URL into `.env` as `CURSOR_WEBHOOK_URL`.

## CLI

```bash
# Scan gigs 21–28 days out (lists needs_generation for new/not-started gigs)
python3 flyer_generator.py --scan

# Auto: generate + iMessage review link for eligible gigs in window
python3 scripts/auto_scan.py

# Test mode (mock data when lindseylane.com is down)
python3 flyer_generator.py --test --scan
export GIG_FLYERS_TEST_MODE=1   # same effect for any script importing gig_calendar

# Generate 3 options for one gig
python3 flyer_generator.py --gig 2026-07-18_stevie-rays-blues-bar --count 3

# Revision
python3 flyer_generator.py --gig {id} --base-option B --feedback "bigger venue name"

# Dry run (no OpenAI calls)
python3 flyer_generator.py --gig {id} --dry-run

# Offline end-to-end smoke test
./scripts/run_e2e_live.sh --test
```

### Test mode

When the band website is unreachable, use mock gigs from [`fixtures/mock_gigs.json`](fixtures/mock_gigs.json):

- Pass `--test` to `flyer_generator.py`, or set `GIG_FLYERS_TEST_MODE=1`
- Mock data pins `reference_today` to `2026-06-23` so the 21–28 day window always includes three sample gigs
- Override the fixture path with `GIG_FLYERS_MOCK_PATH` if needed

### Calendar cache

Live fetches from lindseylane.com are slow and unreliable. Parsed events are saved to `cache/calendar.json` with a timestamp.

- **TTL:** `GIG_CALENDAR_CACHE_TTL_SECONDS` (default 6 hours)
- **Stale fallback:** if a live fetch times out, the last good cache is used automatically
- **Interactive `/pick`:** serves cache immediately and refreshes in the background when stale
- **Timeout:** `GIG_CALENDAR_FETCH_TIMEOUT_SECONDS` (default 45)

Warm the cache manually:

```bash
python3 -c "from gig_calendar import get_all_events; get_all_events(force_refresh=True)"
```

The picker page shows a “Calendar cached at …” footnote when serving cached data.

## Web review

After generation, `/send-review` sends an iMessage with a link (not images). The review page shows:

- Current round options with **Approve** and **Revise** forms
- **Regenerate all options** — fresh round from scratch (not tied to A/B/C feedback)
- Full iteration history (all rounds)
- Feedback log

**Regenerate** vs **Revise**: Revise applies feedback to a specific option. Regenerate runs new research + 3 new options as the next round, keeping prior rounds in history.

While generation runs (initial generate, regenerate, or revise), the processing page shows **three option cards** with a live flow per option:

1. **Blue vessel fill** while the image generates (once per attempt)
2. **Image preview** with **green outline** during AI review
3. **Blue outline** when review passes; **red flash** (~0.75s) on fail, then one remake cycle or stop if auto-remake limit reached

Provider label shown (e.g. “Generating with Gemini Nano Banana”). Status streams via SSE with 1s polling fallback.

### AI reviewer

After each option image is generated, an **AI reviewer** (OpenAI vision) checks it before you see it:

- **Text accuracy** — venue, date, band name, time spelled correctly and readable
- **Band photo fidelity** — compares output to the reference publicity photo (no distortion, crop, or member loss)
- **Member visibility** — group shots should show all band members (4 expected)
- Flags AI tells and authenticity failures per `style.yaml`
- Automatically remakes failed options (up to 2 retries per letter)
- Logs verdicts in `state.json` / manifests; review page shows **Passed** or **Remade: …** per option

Disable with `AI_REVIEWER_ENABLED=0`. Model defaults to `gpt-4o-mini` (`AI_REVIEWER_MODEL`).

### Image provider

**Production default:** all options use OpenAI (`GIG_IMAGE_PROVIDER=openai`, `GIG_IMAGE_PROVIDER_SPLIT=0`).

- `openai` — `gpt-image-1` via `images.edit` + `input_fidelity=high` when a band reference photo is available
- `OPENAI_IMAGE_USE_REFERENCE=1` and `OPENAI_IMAGE_INPUT_FIDELITY=high` recommended
- Option C uses `high` image quality by default; A/B use `medium` (override with `OPENAI_IMAGE_QUALITY_CREATIVE`, etc.)

Optional Gemini (`gemini-2.5-flash-image`) remains available but hits tight quotas; OpenAI fallback applies when split mode uses Gemini.

**Per-option split (optional):** `GIG_IMAGE_PROVIDER_SPLIT=1` with `GIG_IMAGE_PROVIDER_A/B/C` — disabled in production while all-OpenAI is active.

Auto-remakes per option: `AI_REVIEWER_MAX_REMAKES=1` (initial + 1 remake, then stops with failed note).

On **approve**: final PNG is emailed and iMessaged to you.

```bash
# Manual approve/revise via API
python3 scripts/process_reply.py "APPROVE B" --web
python3 scripts/process_reply.py "REVISE C: more color" --web
```

## Style authority

All generation follows [`style.yaml`](style.yaml) — the Authentic Band Flyer System doctrine.

Each option A/B/C maps to a **creativity spectrum** with **distinct layout structures** (same engine, different prompts). Options **A, B, and C generate in parallel** (up to 3 workers).

| Option | Tier | Layout character |
|--------|------|------------------|
| A | Conservative | Stacked utilitarian handbill; B&W or one ink; type-heavy |
| B | Medium | Offset paste-up + one accent; muted venue color |
| C | Creative | Collage energy — ticket stub, torn edge, bolder bar tones |

Revision feedback is treated as the **primary directive** at the top of the prompt, with anti-repetition language vs the prior round. Full prompts are saved in each round's `manifest_r{N}.json` for debugging.

### Gig research and band photos

Before generating flyers, the system researches each gig:

- **Venue type** (blues bar, VFW/legion, festival, country bar, etc.)
- **Audience demographics** (heuristic tags)
- **US holiday context** (July 4, Halloween, etc.)
- **Design language** customized per venue (e.g. Stevie Ray's → blues club handbill)

Band publicity photos live in [`bandphotos/`](bandphotos/) (3 photos). `photo_selector.py` picks the best match; the selected photo is passed to OpenAI via **`images.edit` only** (`OPENAI_IMAGE_USE_REFERENCE=1`, `input_fidelity=high`). All tiers include a mandatory **BAND PHOTO FIDELITY** block — the reference photo must appear exactly as provided; flyer design wraps around it without transforming faces, poses, or cropping members.

Research and the selected photo appear on the **review page** context panel and are saved in `state.json` / manifests.

Optional LLM enrichment: set `GIG_RESEARCH_USE_LLM=1` (uses `gpt-4o-mini`).

## Project layout

| Path | Purpose |
|------|---------|
| `gig_research.py` | Venue/holiday/design research heuristics |
| `photo_selector.py` | Band photo scoring from `bandphotos/` |
| `bandphotos/` | Band publicity photos + `manifest.yaml` |
| `fixtures/mock_gigs.json` | Mock calendar for test mode |
| `gig_calendar.py` | Scrape band calendar + disk cache |
| `flyer_generator.py` | OpenAI image generation + `--auto-scan` |
| `scripts/auto_scan.py` | Daily auto mode entry point |
| `scripts/daily-auto-scan.sh` | Cron/launchd wrapper for auto mode |
| `state.json` | Workflow state per gig |
| `bridge/` | FastAPI bridge, web review UI, iMessage + email |
| `output/` | Generated flyers |
| `prompts/` | Cursor Automation drafts |
