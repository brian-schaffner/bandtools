# Wild Design Option — Requirements

## Locked decisions (2026-07-09)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Round size | **3-up: A + B safe, D wild** | Faster/cheaper than 4-up; C drops when wild is on |
| Wild provider | **Gemini** (`GIG_IMAGE_PROVIDER_D=gemini`) | Staging already wired; strong at bold full-image visuals |
| Default exposure | **On in staging** (`WILD_DESIGN_ENABLED=1` in `fly.test.toml`); off in prod until face polish | Safe rollout |
| Approve wild as-is | **Yes**, with UI disclaimer | Face-perfect regen is Phase 3 |
| Wild letter | **D** | A/B stay familiar safe slots |

Pivot-friendly: all knobs are env-driven; classic A/B/C returns when `WILD_DESIGN_ENABLED=0`.

---

## Product concept

Each generation round offers **two safe structured options** plus **one fully designed wild option**:

| Slot | Label | Pipeline | Face rules |
|------|-------|----------|------------|
| **A** | Safe — conservative | Structured layout | Strict fidelity |
| **B** | Safe — medium | Structured layout | Strict fidelity |
| **D** | Wild — fully designed | Full-canvas image gen (Gemini) | Distortion OK for now |

Wild option D is **not bound** by fixed templates, reference-compose, or photo-fidelity doctrine. It designs the entire poster as one AI image — typography, graphics, and band depiction together.

---

## Phase 1 — Wild option in every round (MVP)

### Generator
- `WILD_DESIGN_ENABLED=1` → round letters `(A, B, D)` instead of `(A, B, C)`
- `STRUCTURED_LAYOUT_OPTIONS=A,B` when wild on (D never structured)
- New `wild_design/prompt.py`: full-canvas prompt; no photo-fidelity block; allows stylization
- D generates via image API **without** reference photo compose
- `generation_mode: full_canvas_wild` in manifest / per-option metadata
- AI reviewer: **text legibility only** for wild — skip automated photo-fidelity checks

### Agent UI
- Option D card badge: **Fully designed · experimental**
- Subtext: *Faces may not match the band photo*
- Chat / approve / revise support option **D**

### Revision semantics (Phase 1)
- Revise **A or B** → existing structured fan-out (unchanged)
- Revise **D** → 3 new full-image generations with feedback (same wild prompt path)

### Env (staging)
```
WILD_DESIGN_ENABLED=1
WILD_DESIGN_OPTION=D
GIG_IMAGE_PROVIDER_D=gemini
STRUCTURED_LAYOUT_OPTIONS=A,B
```

---

## Phase 2 — Wild revision polish

- **D fan-out revisions** automatically run `wild_band_replace`: prior D poster + reference band photo → Gemini swaps in your band while keeping the design
- User feedback (e.g. “more neon”) is merged into the band-replace prompt
- Env: `WILD_BAND_REPLACE_ON_REVISE=1` (default on)
- Chat confirms band-swap semantics for Option D

---

## Phase 3 — Face-perfect regen (deferred)

When user picks wild D but faces are wrong:

1. **Lock design** — wild poster as composition/style reference
2. **Face polish** — inpaint/swap face regions from reference band photo, or regen-with-constraint
3. New action: *"Polish faces on D"* (or prompt after approve)
4. Store `wild_original_path` / `wild_polished_path`

Not in scope until Phases 1–2 ship.

---

## Out of scope (for now)

- Replacing A/B with a single safe option
- OpenAI wild fan-out (Gemini only for D; pivot via env)
- Blocking approve on D without face polish
- Production enable without explicit flag

---

## Success criteria (Phase 1)

- [ ] Generate round produces A, B structured + D wild image
- [ ] D visibly different from A/B (full composition, not handbill template)
- [ ] Agent shows experimental badge on D
- [ ] `approve D` works
- [ ] `revise D — more neon` starts wild fan-out job
- [ ] Reviewer does not fail D on face drift
