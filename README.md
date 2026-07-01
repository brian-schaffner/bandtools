# Band Tools

Multi-component app for Lindsey Lane Band: **Setlist Loader** + **Gig Flyers**, served from a single Fly.io deployment.

## Architecture

```
https://bandtools.fly.dev
    │
    ├── /                 → Next.js hub (setlist-helper)
    ├── /setlist-loader   → Setlist Loader UI
    ├── /api/*            → FastAPI (server_simple_db)
    └── /flyers/*         → Gig Flyers bridge (in-process)
```

All three services run in one container via **supervisord** + **nginx** on port `8090`.

## Local development

Use the original repos for day-to-day dev:

- `setloader/` — backend + frontend source
- `gig-flyers/` — flyer generation + bridge

Or run components individually from this monorepo (see each subfolder README).

## Deploy

### Test (staging)

```bash
cp .env.example .env   # fill in secrets
FLY_CONFIG=fly.test.toml ./scripts/fly-deploy.sh
./scripts/smoke-test.sh https://bandtools-test.fly.dev
```

### Production

After smoke tests pass:

```bash
FLY_CONFIG=fly.toml ./scripts/fly-deploy.sh
./scripts/smoke-test.sh https://bandtools.fly.dev
```

## Fly apps

| App | URL | Volume |
|-----|-----|--------|
| `bandtools-test` | https://bandtools-test.fly.dev | `bandtools_test_data` |
| `bandtools` | https://bandtools.fly.dev | `bandtools_data` |

## Required secrets

Set via `.env` (deploy script pushes to Fly for **both** `bandtools` and `bandtools-test`):

- `SECRET` / `NEXT_PUBLIC_API_SECRET`
- `OPENAI_API_KEY`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
- `BRIDGE_SECRET` (defaults to `SECRET`)

OAuth redirect URI is set automatically per app: `https://{app}.fly.dev/auth/google/callback`

Add **both** redirect URIs in [Google Cloud Console](https://console.cloud.google.com/) → Credentials → your OAuth client:

- `https://bandtools.fly.dev/auth/google/callback`
- `https://bandtools-test.fly.dev/auth/google/callback`
