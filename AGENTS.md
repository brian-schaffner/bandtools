# Band Tools

Monorepo with three services that are deployed together (via `supervisord` + `nginx`) but are run
individually during development. See `README.md` and each subfolder for product details.

## Cursor Cloud specific instructions

### Services & how to run them (dev mode)

Three services must run for the full product. Each uses its own environment; run each from its own directory.

| Service | Dir | Dev run command | Port |
|---------|-----|-----------------|------|
| Setlist Loader API (FastAPI) | `setloader` | `.venv/bin/uvicorn server_simple_db:app --host 127.0.0.1 --port 8002` | 8002 |
| Gig Flyers bridge (FastAPI) | `gig-flyers` | `GIG_FLYERS_TEST_MODE=1 .venv/bin/uvicorn bridge.server:app --host 127.0.0.1 --port 8010` | 8010 |
| Band Tools hub / Setlist Loader UI (Next.js) | `setloader/setlist-helper` | `npm run dev` | 3002 |

Open the app at `http://localhost:3002` (hub → "Setlist Loader" and "Gig Flyers").

### Non-obvious caveats

- **Python deps live in per-service venvs**: `setloader/.venv` and `gig-flyers/.venv` (each has a
  separate, conflicting dependency set — do not share one venv). The update script recreates/refreshes them.
- **`gig-flyers` needs runtime dirs before it starts**: `bridge.server` mounts `output/` as static files
  at import time and reads `state.json`. In dev, create them first:
  `mkdir -p gig-flyers/{output,cache,logs} && [ -f gig-flyers/state.json ] || echo '{}' > gig-flyers/state.json`.
  (In the Docker/Fly image this is done by `scripts/fly-entrypoint.sh`, which isn't used locally.)
- **Run the flyers bridge with `GIG_FLYERS_TEST_MODE=1`** locally so it uses `fixtures/mock_gigs.json`
  instead of fetching the live band calendar over the network.
- **No external API keys are configured by default.** Flows that call OpenAI/Google (setlist PDF
  extraction via `/standalone/pdf-extraction` and actual flyer image generation) will fail without
  `OPENAI_API_KEY` / `GOOGLE_API_KEY`. Fully-offline core flows that work without keys: dev login
  (`POST /auth/login`), Song Book Pro backup verification (`/verify_backup`, parses `.sbpbackup` ZIPs
  locally), catalog/title-validation, and the Gig Flyers home/picker pages in test mode.
- **Dev login**: the UI "Sign In" button falls back to a hardcoded dev user (`brian@schaffner.net`) when
  Google OAuth is unconfigured — no real Google account needed.
- **Frontend env**: `setloader/setlist-helper/.env.local` sets `NEXT_PUBLIC_API_URL=http://localhost:8002`
  so the UI talks directly to the Setlist Loader API in dev (in prod, nginx routes `/api`). This file is
  gitignored and lives in the VM snapshot.
- **`next lint` is not usable non-interactively**: ESLint is not configured in the repo, so `npm run lint`
  prompts to set it up. Builds ignore lint/TS errors (`next.config.mjs`).

### Tests

- `gig-flyers`: `cd gig-flyers && .venv/bin/python -m pytest tests/ -q`. Many tests require live
  OpenAI/Gemini keys + network and will hang/fail offline (the repo's `scripts/smoke-test.sh` treats them
  as skippable). Offline-clean subset: `test_text_validation.py test_gen_timing.py test_job_status.py
  test_fill_progress.py test_calendar_cache.py` (needs the runtime dirs above).
- `setloader/tests/test_server.py` targets the legacy `server.py` and needs a gitignored
  `tests/data/sample.pdf` fixture that is not in the repo, so it fails locally (not an env problem).
- `pytest` is installed into both venvs by the update script.
