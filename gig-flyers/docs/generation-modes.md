# Generation modes and profiles

Set **`GIG_FLYERS_PROFILE`** once; explicit env vars always win over profile defaults (`setdefault`).

## Profiles

| Profile | Use | Round layout | Primary recipes |
|---------|-----|--------------|-----------------|
| **`staging-wild`** | Band Tools staging (`fly.test.toml`) | `three_canvas` — A/B/C all wild | Gemini wild tiers + convert + assurance |
| **`prod-safe`** | Local / production structured flyers | A/B/C structured | Fixed templates + OpenAI reference compose |

### `staging-wild` (default on staging)

- `WILD_DESIGN_ENABLED=1`, `WILD_ROUND_LAYOUT=three_canvas`
- Gemini for A/B/C; OpenAI for band convert
- `WILD_COLOR_CORRECT=1`, `WILD_FACT_LOCKS=1`, `FLYER_LOGO_OVERLAY=1`
- `ASSURANCE_ENABLED=1`, `ASSURANCE_FACT_GATE=1`, `ASSURANCE_HEADER_GHOST=1`
- Flyer Agent LLM chat enabled

### `prod-safe`

- Wild off; `STRUCTURED_LAYOUT_OPTIONS=A,B,C`
- `USE_FIXED_TEMPLATES=1`, `LAYOUT_BACKEND=pictex`
- All-OpenAI image path with reference photo fidelity
- Assurance on; wild color correct off

## Generation recipes (manifest `generation_mode`)

| Mode | Description |
|------|-------------|
| `structured_fixed` | PicTex/PIL fixed templates + band photo composite |
| `full_canvas_wild_*` | Wild tiers A/B/C (Gemini text-to-image) |
| `wild_band_replace` | Convert / band swap (dual-image edit) |
| `wild_pil_composite` | Option D shell + exact photo paste |

## Assurance order (wild)

1. Image generation (Gemini / OpenAI)
2. `enrich_wild_poster` — color correction
3. `overlay_flyer_logo` — official lockup
4. AI reviewer — gig-fact gate (wild) + vision QA

## Local override

```bash
export GIG_FLYERS_PROFILE=staging-wild
# or prod-safe
python3 flyer_generator.py --gig <id> --count 3
```

Bridge and `flyer_generator` call `apply_gig_flyers_profile()` after loading `.env`.
