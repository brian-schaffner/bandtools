# Band Tools deploy scripts

Standardized Fly.io deploy entry points for the monorepo.

## Staging (default for development)

**App:** `bandtools-test`  
**URL:** https://bandtools-test.fly.dev  
**Config:** `fly.test.toml`

```bash
./scripts/deploy-staging.sh
```

This runs, in order:

1. Preflight (`fly` CLI + auth)
2. Ensure Fly app and volume exist
3. Sync secrets from `.env` (if present)
4. `fly deploy` with staging config
5. Smoke tests against `/health`, `/flyers/`, etc.

### Options

| Flag | Effect |
|------|--------|
| `--no-smoke` | Deploy only; skip smoke tests |
| `--skip-secrets` | Deploy image without updating Fly secrets |
| `--dry-run` | Print plan; no deploy |
| `--help` | Usage |

### Examples

```bash
# Fast redeploy while iterating (secrets already on Fly)
./scripts/deploy-staging.sh --skip-secrets

# Deploy without waiting on smoke tests
./scripts/deploy-staging.sh --no-smoke

# Verify plan before deploy
./scripts/deploy-staging.sh --dry-run
```

## Production

After staging smoke tests pass:

```bash
FLY_CONFIG=fly.toml ./scripts/fly-deploy.sh
./scripts/smoke-test.sh https://bandtools.fly.dev
```

Production deploy will get the same `scripts/deploy/production.sh` wrapper in a follow-up; use `fly-deploy.sh` for now.

## Layout

```
scripts/
  deploy-staging.sh      # canonical staging entry (wrapper)
  deploy/
    staging.sh           # staging orchestrator
    staging.env          # staging app/url/config constants
    lib.sh               # shared Fly helpers
  fly-deploy.sh          # low-level deploy (staging or prod via FLY_CONFIG)
  smoke-test.sh          # HTTP smoke checks
```

## Secrets

Copy `.env.example` → `.env` and fill values. The deploy script pushes them to Fly when `.env` exists. Without `.env`, existing Fly secrets are kept.

**Gemini (options B/C):** add `GOOGLE_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey). Staging enables split mode (`A=openai`, `B/C=gemini`) via `fly.test.toml`.

Verify locally:

```bash
cd gig-flyers
python3 scripts/gemini_smoke_test.py
```
