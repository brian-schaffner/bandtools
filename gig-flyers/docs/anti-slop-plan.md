# Anti-Slop Plan — Deterministic Flyer Pipeline

## Architecture

```
GigEvent (calendar facts)
        │
        ▼
┌───────────────────────────────────────┐
│  fixed_templates.py                   │
│  A: simple stack │ B: handbill │ C: collage │
│  + finalize_layout_spec (gates)       │
└───────────────────────────────────────┘
        │
        ├─ LAYOUT_BACKEND=pictex (default) ──► pictex_renderer (Option B)
        │                                      fallback → structured_renderer
        │
        └─ structured_renderer (PIL) ──► photo composite + typography
                    │
                    ▼
        validate_structured_flyer
        (overflow, no text-on-photo, footer, bounds)
                    │
                    ▼
               PNG output
```

**AI is optional and narrow:** Art Director LLM coordinates are **off** unless `USE_FIXED_TEMPLATES=0` and `STRUCTURED_LAYOUT_USE_AI=1`. OpenAI may still run Option A compose or optional margin-texture passes — never layout JSON in production.

## Root cause (5 Whys)

Conflated layout/rendering with generative AI. LLM JSON coordinates caused clipped headers, text on faces, duplicate footer facts, and heavy cream washout.

**Fix:** gig facts → fixed template → photo composite → optional margin decoration only.

## Phase 1 — Immediate gates (shipped)

| Gate | Implementation |
|------|----------------|
| No LLM layout coords | `USE_FIXED_TEMPLATES=1` (default); `fixed_templates.py` |
| Text never on photo | `layout_geometry.enforce_no_text_on_photo` + validation |
| 48px safe margins | `SAFE_MARGIN_PX`, `clamp_text_element` |
| Max 90% text width | `MAX_TEXT_WIDTH_PCT = 90` |
| Auto-shrink headers | `_fit_text_font` at render time |
| Reduced cream vignette | conservative 0.18, medium 0.12, creative 0.08 |
| Grain via ideamaxfx only | `PHOTO_EFFECTS_BACKEND=ideamaxfx`; PIL cream edge only |
| Post-render validation | `validate_structured_flyer` |

## Phase 2 — PicTex

| Item | Path / flag |
|------|-------------|
| Dependency | `pictex>=2.3.0` in `requirements.txt` |
| Renderer | `structured_layout/pictex_renderer.py` |
| Column slots | header → featuring → photo → date → time → address |
| Env flag | `LAYOUT_BACKEND=pictex` (default for B/C) |
| Fallback | `structured_renderer` if Skia import fails |

## Phase 3 — Narrow AI

| Condition | Art Director |
|-----------|--------------|
| `USE_FIXED_TEMPLATES=1` (default) | **disabled** |
| `LAYOUT_BACKEND=pictex` | **disabled** |
| `STRUCTURED_LAYOUT_USE_AI=1` + `USE_FIXED_TEMPLATES=0` | enabled (experimental) |

Typography-only OpenAI (`OPENAI_IMAGE_PIPELINE=typography_only`) may decorate margins on Option A — not layout JSON.

## Phase 4 — Quality

- Golden test: `test_tuesday_jam_golden_handbill_render` in `tests/test_structured_layout.py`
- Re-render without API:

```bash
cd /Users/brian/dev/gig-flyers
.venv/bin/python scripts/render_template_flyers.py \
  --gig 2026-06-30_stevie-ray-s-tuesday-jam
```

## Environment flags

| Flag | Default | Effect |
|------|---------|--------|
| `USE_FIXED_TEMPLATES` | `1` | Fixed templates; no Art Director coords |
| `LAYOUT_BACKEND` | `pictex` | PicTex for Option B; C uses PIL collage |
| `STRUCTURED_LAYOUT_USE_AI` | off | Opt-in LLM layout JSON |
| `PHOTO_EFFECTS_BACKEND` | `ideamaxfx` | Grain via ideamaxfx; cream edge PIL-only |
| `STRUCTURED_LAYOUT_OPTIONS` | `A,B,C` | Which letters use structured fixed templates |

## Tuesday Jam fixture

- Gig: `2026-06-30_stevie-ray-s-tuesday-jam`
- House jam: Featuring Lindsey Lane Band, 7:30 pm
- Venue: Stevie Ray's Tuesday Jam
- Address: 230 East Main Street Louisville KY 40202

## Shippable criteria (B/C)

- [x] No clipped header text
- [x] No text on band faces
- [x] Cream vignette ≤ 0.18 conservative
- [x] Each fact once (venue, featuring, date, time, address)
- [x] Address in footer
- [x] Tests pass (`test_structured_layout`, `test_text_validation`)
