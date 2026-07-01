# Flyer Pipeline Experiments — 3-Cycle Log

**Date:** 2026-06-25  
**Context:** After 5+ iterations of `images.edit` + photo-on-canvas + mask + `enforce_photo_bbox`, the same failure modes persisted in r11 regen (ghost strips, text clipping, white photo box on cream, wrong zip on conservative).

**Failure PNGs analyzed:**
| Tier | File | Visible defects |
|------|------|-----------------|
| A Conservative | `image-2d976771…` | Time clipped above photo; zip 40002 (should 40202); white/cream photo box |
| B Medium | `image-c4299a25…` | Ghost band strip above photo inside frame; time clipped below photo |
| C Creative | `image-5cfec420…` | Photo in cream box, poor integration; date/time/address mostly correct |

---

## Cycle 1 — Diagnose current pipeline + validation blind spots

### Hypothesis
**H5:** The model sees band pixels in `images.edit` input and redraws faded copies in editable typography zones (header ghosts, footer strips, frames). `enforce_photo_bbox` restores the photo slot but cannot fix layout overlap or typography-zone band imagery that evades detection.

### Experiment design
- Run `validate_flyer_photo` + custom metrics on the 3 failure PNGs (tier-matched compose bbox).
- **Pass:** validation fails on any visible ghost/duplicate/strip.
- **Fail (confirms hypothesis):** validation passes despite visible defects.

### Execution
```bash
python scripts/experiment_flyer_pipeline.py cycle1   # or inline measure_flyer on 3 PNGs
```

### Data

| Image | Tier | validation | drift | duplicate | strip | outside_band | white_cream_Δ | header_noncream% |
|-------|------|------------|-------|-----------|-------|--------------|---------------|------------------|
| conservative failure | A | **PASS** | 2.6 | no | no | no | **42.0** | 34% |
| medium failure | B | **PASS** | 2.7 | no | no | no | **38.7** | **55%** |
| creative failure | C | **PASS** | 2.6 | no | no | no | 4.2 | 100%* |

\*Creative header is intentionally full-bleed designed content, not band duplication.

**Typography zone heights (expected):** header ~473–504px, footer ~189–229px above/below photo slot.

### Analysis
1. **All three user-reported broken flyers PASS automated validation.** This explains why broken art ships after `enforce_photo_bbox`: drift is low (~2.6) because the photo slot is restored, but ghosts in the protection gutter and text-layout errors are invisible to checks.
2. Medium-tier **header_noncream fraction 55%** correlates with the visible ghost/frame inside the blue border — band-like or high-contrast content in the header zone, not caught by template matching.
3. Conservative **white_cream_Δ ≈ 42** quantifies the white studio box on cream paper (integration problem, not duplication).
4. Wrong zip (40002) is a **text/facts** failure — outside `validate_flyer_photo` scope entirely.

### Revised hypothesis (→ Cycle 2)
The pipeline is not salvageable with stronger prompts or post-hoc enforce alone. Two separate failures:
- **Photo duplication class:** model input contains band → partial redraw in editable zones.
- **Validation gap:** thin header ghosts evade `detect_double_band_photo`; text clipping and fact errors are unchecked.

Test **H1 typography-only** (no band pixels to API) and quantify synthetic detection rates.

---

## Cycle 2 — Typography-only (H1) vs synthetic failure injection

### Hypothesis
**H1/H4:** API receives a **blank cream canvas** with an empty photo slot. Model generates typography/graphics only. PIL composites the pre-processed band photo once underneath (transparent hole in photo slot). This removes the model's ability to see or redraw band imagery.

### Experiment design
| Fixture | Simulates | Expected detection |
|---------|-----------|-------------------|
| `synthetic_ghost` | Top strip of photo pasted in header gutter | `detect_double_band_photo` = True |
| `synthetic_strip` | Bottom photo row tiled below bbox | `detect_horizontal_strip` = True |
| `h1_composite` | Fake typography + PIL photo composite | `validate_flyer_photo` = True, drift ≈ 0 |

### Execution
```bash
PYTHONUNBUFFERED=1 python -c "…"  # see scripts/experiment_flyer_pipeline.py cycle2
```

### Data

| Case | duplicate | strip | validate |
|------|-----------|-------|----------|
| synthetic_ghost | **False** (18s scan) | — | would PASS |
| synthetic_strip | — | **True** (3s) | would FAIL strip check |
| h1_composite (fixed hole punch) | no | no | **PASS**, drift **0.0** |

Initial H1 composite failed drift (30.3) because typography opaque cream covered the photo slot. Fixed by punching a transparent hole in the typography layer before `alpha_composite`.

### Analysis
1. **Header ghost detection is broken** — even an obvious synthetic ghost above `photo_bbox` returns `detect_double_band_photo=False`. Footer strips *are* caught.
2. **H1 composite is architecturally sound** — synthetic end-to-end passes all five validation checks with zero drift when photo is pasted without conflicting alpha.
3. Current `images.edit`+mask approach fails not because enforce is weak, but because **the model should never receive band pixels**.

### Revised hypothesis (→ Cycle 3)
Promote H1 to a feature-flagged production path. Test one live API call. Evaluate H3 (cream vignette / white knockout) as a secondary integration fix — not a primary strategy.

---

## Cycle 3 — Live H1 API test + H3 pre-integration

### Hypothesis
**H3:** PIL cream-edge vignette and white-background knockout before compositing reduces white/cream box contrast so the model (or final composite) integrates better.

**H1 live:** One real `images.edit` on blank canvas for option B (medium) should produce a flyer with no ghost/strip and correct photo fidelity.

### Experiment design
- H3: compare `white_cream_delta` on raw vs `apply_photo_preintegration` compose (no API).
- H1 live: `OPENAI_IMAGE_PIPELINE=typography_only`, one OpenAI call, option B only.
- **Pass:** validation PASS; no visible ghost; gig facts readable.

### Execution
```bash
OPENAI_IMAGE_PIPELINE=typography_only python scripts/experiment_compose.py
python scripts/validate_flyer_photo.py output/experiments/typography_only_B.png bandphotos/…jpg --tier medium --json
```

### Data

**H3 pre-integration (local only):**

| Metric | Raw compose | Integrated |
|--------|-------------|------------|
| white_cream_Δ (top edge sample) | 36.6 | 41.0 (↑ worse) |

Pre-integration also caused validation drift failure (30.3 vs threshold 15) because `compose.photo_layer` no longer matches pasted pixels. Disabled by default (`preintegrate=False`).

**H1 live API (option B, medium):**

| Check | Result |
|-------|--------|
| validate_flyer_photo | **PASS** (all 5 checks) |
| photo_bbox_drift | 0.00 |
| duplicate / strip / outside | none |
| Visible ghost/double photo | **none** |
| Zip code | **40202** ✓ |
| Show time "9:30 pm" | **missing** (prompt/compliance gap) |
| White/cream box | still visible |
| Faint slot outline below photo | minor model artifact in slot border |

Output: `output/experiments/typography_only_B.png` (1.5 MB, ~112s generation)

### Analysis
1. **H1 wins** — live test eliminates the dominant failure class (ghost/duplicate band imagery) with perfect automated photo validation.
2. **H3 alone is insufficient** — edge knockout did not reduce white/cream contrast on sampled edge pixels and breaks drift validation. Deprioritize unless recomputed against an updated expected layer.
3. **Remaining gaps are typography QA**, not photo pipeline: missing show time, white box contrast, occasional slot-border artifacts. These need prompt hardening and/or a text-focused reviewer — not more `enforce_photo_bbox` tuning.

---

## Summary Table

| Cycle | Hypothesis | Key result | Verdict |
|-------|------------|------------|---------|
| 1 | H5: photo-in-input causes redraws; validation catches them | **All 3 broken flyers PASS validation**; ghosts undetected | Current architecture + validation broken |
| 2 | H1: blank canvas + PIL composite | Synthetic H1 PASS; synthetic ghost **not** detected | Adopt H1; fix ghost detection separately |
| 3 | H3 pre-integration + H1 live API | H3 worse on Δ metric; **live H1 PASS**, no ghost, correct zip | **Ship H1 behind flag** |

## Winning hypothesis

**H1 — Typography-only generation** (`OPENAI_IMAGE_PIPELINE=typography_only`):

1. PIL builds cream canvas with empty photo slot (no band pixels).
2. `images.edit` adds typography/graphics only.
3. PIL composites band photo under typography (transparent hole in slot).
4. `validate_flyer_photo` confirms single photo, no strips.

This is a reframing of "overlay" as **bottom-layer composite** — the API never sees the band.

## Code added

| Path | Purpose |
|------|---------|
| `image_providers/typography_compose.py` | Blank canvas prep, photo composite, optional pre-integration |
| `image_providers/openai.py` | `typography_only_enabled()` branch in `OpenAIImageProvider.generate` |
| `scripts/experiment_flyer_pipeline.py` | 3-cycle metrics + synthetic fixtures |
| `scripts/experiment_compose.py` | One-shot live typography-only option B |
| `.env.example` | Documents `OPENAI_IMAGE_PIPELINE=typography_only` |

## What to try next

1. **Enable the experimental path for one gig:**
   ```bash
   export OPENAI_IMAGE_PIPELINE=typography_only
   python flyer_generator.py --gig <gig_id> --count 3
   ```
2. **Compare** `output/experiments/typography_only_B.png` to r11 option B side-by-side.
3. **Strengthen typography prompt** — require show time as a dedicated line with minimum footer/header reserved height; consider tier-specific `typo_header_px` guards in prompt.
4. **Fix validation blind spot** — header gutter ghost detector (thin horizontal band correlation above `photo_bbox`, <48px tall).
5. **Separate text QA** — zip/time/address verification via vision reviewer or OCR, not `validate_flyer_photo`.
6. **Optional integration pass** — if white box remains objectionable, apply cream vignette *after* composite with updated drift baseline (not H3 pre-paste).

---

*3 cycles complete. No commits made per instructions.*
