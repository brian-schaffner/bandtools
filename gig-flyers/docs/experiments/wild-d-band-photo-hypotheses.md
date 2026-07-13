# Wild D Band Photo — Hypothesis Experiment

**Date:** 2026-07-13  
**Goal:** Wild option D should look like a fully designed western/outlaw-country poster **and** show the real band with accurate faces — not AI-distorted musicians.

**Reference photo:** `bandphotos/475779793_1030489528887965_3935557413007700748_n.jpg` (four-piece, hands raised — matches staging wild D screenshot).

**Event fixture:** Lindsey Lane Band @ Two Lane Tavern, Jun 28 2026.

---

## Hypotheses

| ID | Approach | Mechanism | Expected strength | Expected weakness |
|----|----------|-----------|-------------------|-------------------|
| **H1** | Two-pass band replace | Initial wild D → Gemini edit with poster ref (IMAGE 1) + band ref (IMAGE 2); swap musicians only | Preserves creative Gemini shell from pass 1 | Gemini may still distort faces; depends on API; slower (2 calls) |
| **H2** | Constrained single-pass | One Gemini call with band photo attached; prompt locks faces as sacred | Single call; more creative integration than PIL | Model may still reinterpret faces despite prompt |
| **H3** | Decomposed PIL composite | Western shell drawn in PIL; exact band photo pasted via `prepare_canvas_with_photo` | **Guaranteed face fidelity**; fast (~2s); passes `validate_flyer_photo` | Less “AI magic” — shell is procedural, not full Gemini art |

**H0 (baseline):** Synthetic wild D with blurred/wrong-color band region — simulates current face-distortion failure mode.

---

## Test methodology

### Automated metrics (primary)

Run:

```bash
cd gig-flyers
python3 scripts/experiment_wild_d_band.py           # H0 + H3 (no API key)
python3 scripts/experiment_wild_d_band.py --live  # + H1 + H2 (needs GOOGLE_API_KEY)
```

Each hypothesis produces a PNG in `output/experiments/wild_d_band/`.

**Scoring** (`wild_design/metrics.py`):

1. **`compose_validation_passed`** — `validate_flyer_photo` (photo bbox drift, no duplicate band, no strips). **Hard gate** for face fidelity.
2. **`band_hist_correlation`** — RGB histogram correlation between poster band region and reference (higher = closer color distribution).
3. **`band_mse`** — mean squared error in band region (lower = closer pixels; secondary because grading/cropping affects this).
4. **`elapsed_sec`** — generation latency.

**Ranking:** `(compose_validation_passed, band_hist_correlation, -band_mse)` descending.

### Qualitative criteria (secondary)

- Western/bar energy readable at phone thumbnail size
- Event facts correct (band, venue, date, time)
- Faces recognizable without zoom
- No duplicate ghost band strips

---

## Results (local run, 2026-07-13)

| Rank | Hypothesis | compose_validation | hist_corr | mse | elapsed |
|------|------------|-------------------|-----------|-----|---------|
| **1** | **H3 PIL composite** | **PASS** (drift 1.0) | **0.967** | — | **~14s** |
| 2 | H0 synthetic wild D | — | 0.178 | 7657 | 0.1s |

*(After fidelity fix: untreated photo paste with cream mat — hist correlation 0.97 vs 0.38 with treated crop.)*

**H1 / H2 live Gemini:** Skipped in cloud agent (no `GOOGLE_API_KEY`). Re-run with `--live` on staging or locally.

### Interpretation

- **H3 wins** on the only metric that directly measures “is this actually our band photo”: `validate_flyer_photo` **PASS** with near-zero bbox drift.
- H0’s lower MSE is misleading — the synthetic baseline uses a blurred copy of the same photo, so pixel error is low but faces are unusable.
- H1 remains valuable as a **revision path** when the user likes a specific Gemini wild shell and asks to swap in the band photo (`WILD_BAND_REPLACE_ON_REVISE=1`).

---

## Production decision

**Staging default:** `WILD_D_BAND_MODE=composite` (H3) in `fly.test.toml`.

| Mode | Env value | When |
|------|-----------|------|
| Composite (default) | `composite` | Initial wild D — exact band photo |
| Constrained | `constrained` | Experiment / A-B vs composite |
| Full canvas | `full_canvas` | Original experimental D (faces may distort) |
| Band replace | `WILD_BAND_REPLACE_ON_REVISE=1` | D fan-out revision on an existing wild poster |

---

## Re-run checklist

1. `python3 scripts/experiment_wild_d_band.py --live` with valid Gemini key
2. Compare H1/H2 PNGs side-by-side with H3
3. On staging: generate → confirm option D shows real faces without revision
4. Revision test: `I like option D — replace the band with my band photo` (H1 path)
