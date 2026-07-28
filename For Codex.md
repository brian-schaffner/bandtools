# For Codex — Band Tools / Gig Flyers handoff

**Repo:** [brian-schaffner/bandtools](https://github.com/brian-schaffner/bandtools)  
**Owner context:** Lindsey Lane Band — concert flyers, setlist tooling, single Fly.io monorepo.  
**North star (staging):** `GIG_FLYERS_PROFILE=staging-wild` on **bandtools-test** — wild full-canvas A/B/C via Gemini, assurance plane, large official logos, Flyer Agent as primary UX.  
**Last updated:** 2026-07-28 (after merges #31–#38).

---

## 1. What this monorepo is

| Surface | URL (staging) | Code |
|--------|----------------|------|
| Hub + auth | https://bandtools-test.fly.dev/ | `setloader/setlist-helper/` (Next.js) |
| Setlist Loader API | `/api/*` | `setloader/server_simple_db.py` |
| Gig Flyers + Flyer Agent | https://bandtools-test.fly.dev/flyers/ | `gig-flyers/bridge/`, `gig-flyers/flyer_agent/` |

**Runtime:** One Docker image — nginx `:8090` → Next.js `:3000`, Setloader `:8002`, Flyers bridge `:8080` (supervisord). Persistent data on Fly volume `/data` (output, calendar cache, setloader DB).

**Production:** `bandtools` app / `fly.toml` — structured `prod-safe` profile; wild stack is staging-first until explicitly promoted.

---

## 2. Requirements & design artifacts (read these first)

### Canonical product / engineering docs (`gig-flyers/docs/`)

| Document | Purpose |
|----------|---------|
| [next-gen-requirements.md](gig-flyers/docs/next-gen-requirements.md) | **North star** for staging-wild: goals, shipped table, P0/P1 backlog |
| [generation-modes.md](gig-flyers/docs/generation-modes.md) | Profiles (`staging-wild` vs `prod-safe`), env reference, assurance order |
| [wild-design-requirements.md](gig-flyers/docs/wild-design-requirements.md) | Wild option history (A/B/D → evolved to three_canvas A/B/C); phases 1–3 |
| [anti-slop-plan.md](gig-flyers/docs/anti-slop-plan.md) | Structured pipeline: fixed templates, PicTex, validation gates |
| [shell-pipeline-performance-plan.md](gig-flyers/docs/shell-pipeline-performance-plan.md) | Shell design studio performance notes |
| [experiments/flyer-pipeline-experiments.md](gig-flyers/docs/experiments/flyer-pipeline-experiments.md) | Experiment log |
| [experiments/wild-d-band-photo-hypotheses.md](gig-flyers/docs/experiments/wild-d-band-photo-hypotheses.md) | Band photo on wild layouts |

### Operational / repo docs

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Monorepo architecture, deploy entry points |
| [gig-flyers/README.md](gig-flyers/README.md) | Flyer modes (auto vs interactive), CLI, reviewer, providers |
| [scripts/deploy/README.md](scripts/deploy/README.md) | Staging deploy, secrets, smoke tests |
| [gig-flyers/logos/README.md](gig-flyers/logos/README.md) | 2026 brand PNG sources → `scripts/install_band_logos.py` |
| [gig-flyers/assets/logos/README.md](gig-flyers/assets/logos/README.md) | Runtime overlay assets |
| [gig-flyers/bandphotos/README.md](gig-flyers/bandphotos/README.md) | Reference photos for convert / structured |
| [setloader/GOOGLE_OAUTH_SETUP.md](setloader/GOOGLE_OAUTH_SETUP.md) | OAuth for hub + Flyer Agent |

### Style & prompts

| Path | Purpose |
|------|---------|
| `gig-flyers/style.yaml` | Authentic flyer doctrine (structured path) |
| `gig-flyers/prompts/` | Cursor automation drafts (daily scan, iteration) |

### Config that *is* requirements

| Path | Purpose |
|------|---------|
| `gig-flyers/config/profiles.py` | Profile bundles (`apply_gig_flyers_profile`) |
| `fly.test.toml` | Staging Fly app + `GIG_FLYERS_PROFILE=staging-wild` |
| `fly.toml` | Production Fly app |

---

## 3. Current state (what works today)

### Staging profile (`staging-wild`)

- **Round layout:** `WILD_ROUND_LAYOUT=three_canvas` — options **A, B, C** are all **full-canvas wild** (Gemini), not structured A/B + wild D.
- **Providers:** Split mode — A/B/C = Gemini; band replace/convert = OpenAI (`GIG_IMAGE_PROVIDER_BAND_REPLACE=openai`).
- **Assurance pipeline** (`gig-flyers/assurance/`): post-render color correct → logo overlay → AI reviewer with fact gate and header-gutter ghost detection.
- **Logos:** User-uploaded 2026 assets in `gig-flyers/logos/`; Docker runs `install_band_logos.py` → `assets/logos/`. Placements in `wild_design/logo_placement.py` (footer hero A/C, top banner B; env `FLY_LOGO_PLACEMENT`).
- **Pass-2 band photos:** `WILD_BAND_REPLACE_AFTER_GEN=1` auto-runs band swap when a reference photo exists.
- **Flyer Agent:** `/flyers/agent` — gig board, chat, generate/revise/approve, convert band, **click-to-enlarge** lightbox on A/B/C thumbnails.
- **Build visibility:** Bottom-right stamp on all pages; `build` object on `/health`, `/api/health`, `/flyers/health`, `/flyers/build`. Image build args via `scripts/deploy/lib.sh` (`BANDTOOLS_BUILD_NUMBER`, git SHA, etc.).

### Entry points (generation)

| Flow | Where |
|------|--------|
| Interactive pick + progress UI | `bridge/interactive.py`, `bridge/review.py` |
| Flyer Agent | `flyer_agent/` + `flyer_generator.py` |
| Core generator | `flyer_generator.py` (wild prompts, overlay, convert) |
| Wild prompts / overlay | `wild_design/prompt.py`, `logo_overlay.py`, `color_correct.py` |
| Structured (prod-safe) | `structured_layout/`, `fixed_templates.py` |

### CI / deploy

- **Workflow:** `.github/workflows/staging-deploy.yml` — on push to `main`, runs wild Gemini regression tests, deploys to `bandtools-test`, smoke checks.
- **Branch naming (cloud agents):** `cursor/<descriptive-name>-980b`.

### Recently merged (Jul 28, 2026)

| PR | Topic |
|----|--------|
| #31 | Staging-wild next-gen (profiles, assurance, fact locks, color correct) |
| #33 | Large logo placements + pass-2 band photos |
| #34 | Install 2026 logos from `gig-flyers/logos/` |
| #35–#36 | Flyer Agent click-to-enlarge + lightbox DOM fix |
| #37 | Build stamp on pages + health APIs |
| #38 | `find_band_logo(variant=lockup\|badge)` — fixes generation crash at logo overlay |

---

## 4. Challenges (historical — expect more of the same)

1. **Generative layout slop** — LLM coordinates caused clipped text and cream washout; production structured path uses fixed templates + validation (`anti-slop-plan.md`).
2. **Wild yellow/cream casts** — Gemini full-canvas outputs need post-render `color_correct.py`; still tune per venue/lighting.
3. **Gig fact accuracy** — venue/date/time typos; mitigated by `fact_locks` in prompts, assurance fact gate, revision brief locks — not 100%.
4. **Band photo fidelity** — wild gen distorts faces; mitigated by OpenAI band replace/convert pass and Agent “My band” flow; face-perfect inpaint is **deferred** (wild-design Phase 3).
5. **Provider split & quotas** — Gemini for creative, OpenAI for edit/convert; staging needs `GOOGLE_API_KEY` / `GEMINI_API_KEY` on Fly.
6. **Monorepo deploy coupling** — one image ships hub + setloader + flyers; any flyers bug blocks “whole app” perception; use build stamp + `/flyers/health` to verify flyers slice.
7. **Calendar reliability** — `gig_calendar.py` + disk cache; staging uses `GIG_FLYERS_TEST_MODE=1` with fixtures — **prod calendar behavior differs**.
8. **UI/HTML agent workspace** — large inline JS in `flyer_agent/ui.py`; lightbox bug was **script running before DOM node existed** — prefer delegated events + lazy DOM lookup for new UI.
9. **Logo pipeline drift** — overlay code called `find_band_logo(variant=…)` before `band_mark.py` implemented it (#38). Keep overlay + resolver in sync.
10. **Stale open PRs** — several draft PRs predate three_canvas and logo folder; do not merge blindly (see §6).

---

## 5. Current issues & gaps

### Known / watch

| Issue | Notes |
|-------|--------|
| **Staging test mode** | `fly.test.toml` sets `GIG_FLYERS_TEST_MODE=1` — calendar may be mock/fixture-driven; confirm before judging “real gig” behavior. |
| **Open PR clutter** | #30, #32, and older agent/option-C PRs may conflict with `main`; treat as archive unless rebased. |
| **Filename typo** | Dark logo upload: `Lindset Lane Band Logo 2026...` — installer hard-codes that name. |
| **prod-safe vs staging-wild** | Production not on wild three_canvas until profile/env explicitly changed. |
| **P0 backlog** (from next-gen doc) | Hybrid typography pass; golden gig CI fixtures; venue address KB; multi-reference band convert. |
| **Setlist Loader** | Not the focus of recent work; verify OAuth and `/api/health` if touching nginx or deploy. |

### Verify after each deploy

```bash
curl -sS https://bandtools-test.fly.dev/flyers/health | jq '{status, build, gemini: .providers.gemini_configured}'
./scripts/smoke-test.sh https://bandtools-test.fly.dev
```

Interactive: generate a round at `/flyers/pick` or `/flyers/agent` — confirm no error after “Saved option”, logos visible, build stamp updated.

---

## 6. Open PRs (as of 2026-07-28)

**Merged / authoritative:** `main` through PR **#38**.

**Still open (likely stale — review before merge):**

| PR | Title | Note |
|----|--------|------|
| #32 | New band logo install path | Superseded by #34 (`gig-flyers/logos/` + `install_band_logos.py`) — **close** |
| #30 | Post-render color correct | Largely in #31 — **close or rebase** |
| #17 | Flyer Agent v2 MVP | Partially on `main`; reconcile before merge |
| #3–#6, #10–#13 | Older flyers/hub fixes | May be obsolete |

---

## 7. Key code map (quick navigation)

```
gig-flyers/
  flyer_generator.py      # Orchestration: gen, revise, wild, overlay, convert
  config/profiles.py      # staging-wild / prod-safe
  assurance/              # pipeline, fact_locks, facts (reviewer gate)
  wild_design/            # prompts, logo_placement, logo_overlay, color_correct, band_replace
  structured_layout/      # band_mark.find_band_logo, PicTex, templates
  bridge/server.py        # FastAPI routes, /health, /build
  bridge/ui.py            # Shared HTML chrome + build stamp footer
  flyer_agent/ui.py       # Agent workspace + chat JS
  logos/                  # Source PNGs (2026 brand)
  assets/logos/           # Built overlay PNGs

setloader/
  server_simple_db.py     # API + /health build info
  setlist-helper/         # Next.js hub; components/build-stamp.tsx

scripts/
  deploy-staging.sh       # Canonical staging deploy
  deploy/lib.sh           # fly deploy + build args
  write_build_info.py     # /app/build-info.json at image build
  smoke-test.sh
```

---

## 8. How to develop (Codex / agents)

1. **Branch:** `cursor/<topic>-980b` off `main`.
2. **Flyers tests:** `cd gig-flyers && python3 -m pytest tests/ -q` (CI runs wild Gemini subset before deploy).
3. **Deploy staging:** `./scripts/deploy-staging.sh --skip-secrets` when secrets already on Fly.
4. **Pre-commit:** Hook may fail with `invalid variable name` — team has used `git commit --no-verify` sparingly; fix hook if it blocks often.
5. **Do not** assume `.git` is in Docker build context (`.dockerignore` excludes it) — build metadata comes from **build-args**, not `git` inside Dockerfile.

---

## 9. Opinion — how to proceed

### Immediate (stability + trust)

1. **Close superseded PRs** (#30, #32) and add a one-line note in PR body pointing to #31 / #34.
2. **Golden path test:** One pytest or smoke script that runs a **dry-run** or fixture gig through `enrich_wild_poster` + `overlay_flyer_logo` (regression for `variant` and missing assets).
3. **Confirm staging calendar policy:** Decide whether `GIG_FLYERS_TEST_MODE=1` on staging is still desired; if not, flip in `fly.test.toml` and warm cache on deploy.

### Next product value (aligns with P0 in next-gen-requirements)

1. **Hybrid typography** — generate background-only wild art, render date/venue/band with deterministic PIL/PicTex in reserved zones (reduces fact typos more than prompt locks alone).
2. **Golden gig fixtures** — Two Lane Tavern / Tuesday Jam as CI snapshots (prompt hash + optional image diff thresholds).
3. **Flyer Agent as default** — gradually retire duplicate flows in bridge review UI (#31 backlog: unify review into agent views).
4. **Logo UX** — Already large placements; tune `FLY_LOGO_PLACEMENT` and contrast sampling if logos look small or wrong variant on busy backgrounds.

### Production promotion

- Do **not** point `bandtools` (prod) at `staging-wild` until: wild fact gate metrics are acceptable on real gigs, Gemini keys and cost are budgeted, and `prod-safe` remains the rollback profile (`GIG_FLYERS_PROFILE=prod-safe` in `fly.toml`).

### What not to do first

- Re-open LLM layout coordinates for structured options (regression to anti-slop failures).
- Merge old Option C / procedural composer PRs without rebasing on `three_canvas` + assurance stack.
- Large Flyer Agent UI rewrite without extracting JS from `ui.py` incrementally (high regression risk for chat, job polling, lightbox).

---

## 10. Contacts & secrets (no values here)

Secrets live in Fly / `.env`: `OPENAI_API_KEY`, `GOOGLE_API_KEY` or `GEMINI_API_KEY`, Google OAuth, `SECRET`, `BRIDGE_SECRET`. Staging split providers require Gemini configured — smoke test warns if missing.

**Staging URL:** https://bandtools-test.fly.dev  
**Flyer Agent:** https://bandtools-test.fly.dev/flyers/agent  
**Production URL:** https://bandtools.fly.dev  

---

*This file is the living handoff for Codex (or any agent). Update it when profiles, north star, or deploy contracts change.*
