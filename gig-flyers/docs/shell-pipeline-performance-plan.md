# Shell Pipeline Performance Plan

## Problem

A full shell studio run (pass 1 → pre-pass mockup → user route choice → final pass → eval card) feels too slow for interactive testing. Most wall-clock time is **sequential OpenAI `images.edit` calls** on 1024×1536 PNGs, not local PIL work.

This plan separates what can be **batched ahead of time** from what must stay **gig-specific at runtime**, and targets the highest-impact cuts first.

---

## Current pipeline (as implemented)

```
User clicks Run
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ PASS 1  (~45–120s)                                          │
│  build_shell_briefing_sheet (PIL, ~0.5s)                    │
│  generate_design_shell_openai  → 1× images.edit (high)       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ PRE-PASS  (~15–60s)                                         │
│  personalize_shell_typography_sequential                    │
│    • deterministic PIL text (hybrid: venue/date/time/support)│
│    • 1× images.edit per openai_text_slots (prepass/low)     │
│    • hybrid shells → usually 1 call (HEADLINER only)          │
└─────────────────────────────────────────────────────────────┘
    │
    ▼  [user waits — job status: awaiting_route]
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ FINAL PASS  (~30–120s)                                      │
│  build_personalize_canvas  ← called twice on photo route    │
│  personalize_shell_*                                        │
│    • hybrid photo: canvas + deterministic text + 1× OpenAI   │
│    • hybrid text-only: deterministic + 1× OpenAI HEADLINER  │
│    • openai-only (legacy): up to 5 sequential slot edits    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ EVAL CARD  (~1–2s, PIL only)                                │
└─────────────────────────────────────────────────────────────┘
```

### Typical OpenAI call budget (hybrid shell, e.g. Hendrix)

| Step      | Calls | Quality | Gig-dependent? |
|-----------|-------|---------|----------------|
| Pass 1    | 1     | high    | **No** (shell only) |
| Pre-pass  | 1     | low     | Yes (text) |
| Final     | 1     | high    | Yes (text) |
| **Total** | **3** |         | |

21 of 23 design families use `text_engine: hybrid` → only **HEADLINER** goes through OpenAI on pass 2. Pre-pass repeats the same HEADLINER edit at lower quality before the user even chooses a route.

### Known local waste (no API, but adds latency)

1. **`build_personalize_canvas` runs twice** on photo route: once in `_run_final_pass` for preview, again inside `personalize_shell_photo_registry`.
2. **Pre-pass duplicates final typography work** for hybrid shells (deterministic facts + HEADLINER preview that final pass replaces).
3. **Pass 1 regenerated every run** even though output is `{shell_id}_design_shell.png` and does not depend on gig.
4. **Briefing sheets rebuilt** every pass 1 (cheap, but cacheable).
5. **No step timing** in job summary — hard to know which phase is slow in production.

---

## Bottleneck ranking

| Rank | Bottleneck | Est. share of wait | Fix type |
|------|------------|-------------------|----------|
| 1 | Pass 1 OpenAI (cold every run) | 35–45% | **Pre-batch / cache** |
| 2 | Final pass OpenAI (HEADLINER) | 25–35% | Keep (quality-critical) |
| 3 | Pre-pass OpenAI (redundant HEADLINER) | 15–25% | **Remove or PIL-only** |
| 4 | Duplicate canvas compose | 3–8% | **Deduplicate** |
| 5 | Hero illustration PIL pipeline | 2–5% | Pre-batch band layers |
| 6 | Eval card | <2% | Defer / async |

---

## Strategy: three tiers of work

### Tier A — Shell-static (batch ahead of time)

Independent of gig, band photo, and route. Safe to precompute for all ~23 shells.

| Artifact | Path pattern | Module |
|----------|--------------|--------|
| Briefing sheet | `{shell_id}_pass1_briefing.png` | `design_shell_generate.build_shell_briefing_sheet` |
| Pass 1 design shell | `{shell_id}_design_shell.png` | `generate_design_shell_openai` |
| Slot masks (5) | `{shell_id}_mask_{label}.png` | `shell_pass2_mask.build_slot_mask` |
| Full personalize mask | `{shell_id}_pass2_mask.png` | `build_personalize_mask` |
| Render spec JSON | `{shell_id}_render_spec.json` | `get_render_spec(shell).to_dict()` |

**Batch command (new):**

```bash
./scripts/warm-shell-cache.sh              # all shells
./scripts/warm-shell-cache.sh hendrix_*    # one shell
```

Runs pass 1 only when cache missing or `--force`. Stores manifest with model + prompt hash for invalidation.

### Tier B — Band-static (batch once per band / photo hash)

Depends on band photo + logo, not on gig text.

| Artifact | Key | Notes |
|----------|-----|-------|
| Processed hero illustration layer | `{photo_hash}_{design_family}.png` | threshold/duotone/halftone |
| Tinted logo badge | `{logo_hash}_{shell_id}.png` | palette-matched |
| Default photo + logo paths | env / band profile | already mostly static |

Can warm for default band photo on deploy or first request.

### Tier C — Gig-specific (must run at job time)

| Work | Can optimize |
|------|----------------|
| Deterministic venue/date/time/support text | Already PIL — keep |
| OpenAI HEADLINER (final) | 1 call — keep for quality |
| Route-specific canvas (photo vs text-only) | Prefetch **both** during user review pause |
| Eval card | Build async after showing final image |

---

## Implementation phases

### Phase 1 — Quick wins (1–2 days, no architecture change)

**Goal: cut perceived wait 40–60% on repeat shell testing.**

1. **Pass 1 cache reuse**
   - In `_run_pass1`, if `{shell_id}_design_shell.png` exists and manifest prompt hash matches, skip OpenAI.
   - Env: `SHELL_PASS1_CACHE=1` (default on staging).

2. **PIL-only pre-pass for hybrid/deterministic**
   - New `build_prepass_mockup_deterministic()` — no OpenAI.
   - Apply deterministic text to pass 1 shell; leave HEADLINER placeholder or use plain PIL band name.
   - UI copy: “Text preview — stylized headliner renders on final pass.”
   - **Saves 1 API call (~20–40s)** on 21/23 shells.

3. **Deduplicate canvas compose**
   - `_run_final_pass` stores compose context from first `build_personalize_canvas`; pass into `personalize_shell_photo_registry`.
   - **Saves ~3–8s** on photo route.

4. **Step timing in job summary**
   - Record `timings_ms: { pass1, prepass, final, eval }` in job JSON.
   - Show in results UI + log lines.

**Expected result (Hendrix re-run with warm pass 1):**

| Before | After |
|--------|-------|
| ~3–5 min | ~1–2 min to route choice, ~40–80s final |

---

### Phase 2 — Background warming service (2–3 days)

**Goal: first run of any shell is also fast.**

1. **`scripts/warm-shell-cache.sh`**
   - Iterates `all_shells()`; runs pass 1 + mask precompute for missing entries.
   - Hook into `./scripts/deploy-staging.sh` post-deploy (optional flag `--warm-shells`).

2. **Band asset warm on startup**
   - On bridge startup (staging/test): preprocess default band photo for each `photo_style=hero_illustration` family.
   - Store under `cache/shell_assets/{photo_hash}/`.

3. **Prefetch during `awaiting_route`**
   - Background thread after pre-pass:
     - Compose photo canvas (photo_logo path)
     - Apply deterministic gig text to both variants
   - Final pass becomes HEADLINER-only OpenAI + enforce layers.

**Expected result:** Route choice → final done in **~30–60s** (one high-quality API call).

---

### Phase 3 — Pipeline restructure (3–5 days)

**Goal: treat shells like templates, not generative one-offs.**

1. **Split job types**
   - `shell_pass1` — rare, cacheable, can run offline
   - `shell_personalize` — gig + route only (user-facing)

2. **Studio UX: pick cached shell first**
   - Shell gallery shows pre-generated pass 1 thumbnails.
   - “Run” skips pass 1 when cache hit → straight to pre-pass / personalize.

3. **Optional pass 1 refresh**
   - Explicit “Regenerate design shell” button (invalidates cache).

4. **Eval card lazy load**
   - Return final flyer immediately; eval panel loads via secondary poll.

---

### Phase 4 — Advanced (only if still slow)

1. **Single multi-zone OpenAI edit** for `text_engine: openai` shells (5 slots → 1 call). Higher risk of bleed; feature-flagged.

2. **Parallel slot edits** — 5 concurrent `images.edit` calls on copies, merge zones. Faster but 5× API cost; only for batch production.

3. **Pass 1 model downgrade for cache warm** — use `gpt-image-1-mini` for cache population, `gpt-image-2` only on explicit regen.

---

## Recommended batch jobs

| Job | When | Command |
|-----|------|---------|
| Staging deploy | Every merge to shell branch | `./scripts/deploy-staging.sh` |
| Shell pass 1 warm | After deploy + nightly | `./scripts/warm-shell-cache.sh` |
| Band asset warm | After deploy | `./scripts/warm-shell-assets.sh` |
| Smoke + timing check | After warm | `./scripts/smoke-test.sh` + inspect one Hendrix job timings |

---

## Metrics to track

Add to job summary (`shell_runner.py`):

```json
{
  "timings_ms": {
    "pass1": 87234,
    "prepass": 12400,
    "final": 45100,
    "eval": 890,
    "openai_calls": 2
  },
  "cache_hits": {
    "pass1": true,
    "prepass_openai": false
  }
}
```

Success criteria:

- **Repeat shell test (same shell, different gig):** < 90s to `awaiting_route`, < 60s final pass
- **Cold shell (cache miss):** pass 1 still ~60–90s, but pre-pass < 5s (PIL-only)
- **OpenAI calls per full run (hybrid):** 2 (pass 1 + final HEADLINER), down from 3

---

## Priority recommendation

Start with **Phase 1 items 1–3** — they are low-risk, align with the deterministic architecture, and directly address “takes too long while I’m testing” without waiting on infra.

Phase 2’s deploy hook pairs naturally with the new `./scripts/deploy-staging.sh` workflow.

---

## Out of scope (for now)

- Parallel OpenAI calls on production Fly 1GB VM (memory + rate limits)
- Caching pass 1 across different OpenAI models (invalidates on model plan change)
- Skipping final HEADLINER OpenAI (quality regression for Fillmore/Hendrix)
