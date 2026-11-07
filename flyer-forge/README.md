# Gig Flyer Studio

A band's gig calendar and flyer design tool for one band. Every gig on the calendar keeps its venue, logistics schedule, flyers and set lists together, so past shows form a consistent history. Flyer concepts come from real print traditions rather than generative image models, and band photos and logos are placed pixel-for-pixel from the originals.

## What it does

- **Calendar**: month view plus upcoming and history lists. Each gig page holds:
  - venue details and logistics (contact, deal, notes),
  - a run-of-show schedule (with a "typical club night" template),
  - its flyers,
  - its set lists.

  Import existing gigs from any `.ics` calendar export (re-importing updates instead of duplicating). Export the whole calendar as `.ics`.
- **Set lists**: the loader takes pasted text, `.txt`/`.csv` uploads, or a copy of a previous gig's list. It recognises:
  - numbering and bullets,
  - `Set 1` / `Encore` headers,
  - keys like `[E]`,
  - durations like `3:45`,
  - `->` segues.

  Edit as rows or as text, see per-song play history, and print a big-type stage copy.
- **Flyers stay in sync with the calendar**:
  - A flyer is always filed under a gig. Starting one from a gig pre-fills its details; starting one on its own files it under the gig with the same date and venue, creating that gig if needed.
  - Editing gig details in a flyer updates the calendar too.
  - If the calendar changes later, the gig page and the flyer editor flag the flyer as out of date and offer a one-click update.
- **Band kit**: upload and manage logos and photos (group and individual, tagged by member). Originals are stored byte-for-byte, chunked, and verified with SHA-256 on upload and on every load. Only metadata can be edited (name, members, focal point, primary).
- **References**: an editable rulebook seeded with 11 "AI tells to avoid" and 8 traditional print styles to borrow from. Every AI prompt and the automated review use it.
- **New flyer, in three stages**:
  1. Gig details.
  2. Three design concepts, shown as wireframes first.
  3. Layer in your photo and logo, with treatment, inks and type.
- **Editor**:
  - Layers and an immutable version tree.
  - Plain-language iteration ("bigger date, black and white photo").
  - Evolve ×4 with locks, and fresh concepts.
  - Automated review: fidelity, contrast, hierarchy and legibility.
  - Optional Claude art-director critique.
  - Export to 300 dpi PNG, a print PDF with ⅛" bleed and crop marks, or social formats.

### Fidelity guarantees

Photos and logos are never regenerated. The renderer only applies:

- uniform scale and crop (the aspect ratio is never distorted),
- clip masks (rect, ellipse, arch, slant),
- per-pixel colour mapping (mono, duotone, tint, threshold, logo recolour).

Export is refused if any placement is non-uniform or an original fails its hash check.

## Access and limits

- Every API route verifies the signed-in viewer, and cross-site writes are refused:
  - **On Fly.io** (or anywhere `AUTH_PROVIDER=google` is set), people sign in with Google. Only emails listed in `ALLOWED_EMAILS` get in. If sign-in isn't fully configured, the app refuses every request.
  - **On Cursor's hosting**, publish as private or team. The helper in `cursor/identity.ts` verifies the identity Cursor's hosting passes to the app.
- Locally there is no host gate, so the helper simulates an invented viewer (`cursor/identity.dev.ts`).
- Claude calls are limited to 40 an hour and 200 a day per person. Calendar imports are limited to 20 an hour.
- Storage caps:
  - 2 GB and 600 band-kit files in total,
  - 400 versions per flyer,
  - 1,000 flyers,
  - 3,000 gigs and 3,000 set lists.
- Image previews and thumbnails are only served when their bytes are a real JPEG, PNG or WebP image, with `nosniff` and a sandboxing Content-Security-Policy.

## Running locally

```bash
npm install
npm run dev        # http://localhost:4317
```

Without `DATABASE_URL`, data is stored in an embedded Postgres (PGlite) at `.data/pglite`. With `DATABASE_URL` set, migrations in `migrations/` are applied by `node scripts/migrate.mjs`, which runs as part of `npm run build`.

### AI (optional)

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Enables Claude-directed concepts, iteration, vision critique and reference analysis. |
| `ANTHROPIC_MODEL` | Overrides the default model (`claude-sonnet-5-5`). |

Without a key, everything still works using the built-in art direction, keyword editor and automated checks.

## Deploying to Fly.io

The app runs as a single machine and keeps its data in embedded Postgres (PGlite) on a Fly volume. If you set `DATABASE_URL` to a Postgres database instead, migrations run on boot.

1. In Google Cloud Console, create an OAuth client of type "Web application". Add `https://<app>.fly.dev/api/auth/callback` as an authorised redirect URI.
2. Create the volume and set the secrets:

```bash
fly volumes create gfs_data --size 3 --region iad --app <app>
fly secrets set --app <app> \
  GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... \
  AUTH_SECRET=$(openssl rand -hex 32) \
  ALLOWED_EMAILS="you@example.com,bandmate@example.com" \
  APP_URL=https://<app>.fly.dev \
  ANTHROPIC_API_KEY=...   # optional
```

3. Deploy:

```bash
fly deploy --app <app>
```

## Scripts

- `npm run dev`: dev server on port 4317
- `npm run build`: production build, then migrations
- `npm run lint` / `npm run typecheck`
