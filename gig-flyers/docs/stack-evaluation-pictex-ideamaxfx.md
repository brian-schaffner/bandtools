# Stack Evaluation: PicTex & ideamaxfx

One-page comparison for gig-flyers structured layout (options B/C) vs current PIL pipeline.

## PicTex (layout) vs structured_renderer + OpenAI Art Director

| | **Current** | **PicTex** |
|---|---|---|
| Layout source | OpenAI JSON spec → custom `structured_renderer` (PIL) | Flexbox-style tree → Skia raster |
| Determinism | Good after `finalize_layout_spec`; AI placement varies | High — same tree → same pixels |
| Typography | Helvetica Bold Condensed, manual wrap/clamp | Real font shaping, flex reflow |
| Risk | Art Director drift, duplicate text, overlap heuristics | New dependency, migration of `LayoutSpec` schema |
| Best fit | Already shipping B/C | Phase 2 when B/C need pixel-perfect repeatability |

**Takeaway:** Keep Art Director for creative variation; PicTex is the long-term renderer if we want InDesign-like flex layout without LLM placement noise.

## ideamaxfx EffectsPipeline vs reference_compose PIL hacks

| | **Current (`reference_compose`)** | **ideamaxfx** |
|---|---|---|
| Grain / vignette | Ad-hoc PIL loops in compose path | `EffectsPipeline` presets |
| Halftone | Custom `_apply_halftone` in structured_renderer | Built-in — **do not use on band photos** (r5 lesson) |
| Integration | Option A compose only | Drop-in post-render for B/C backgrounds |
| Risk | Low — known code paths | Medium — new package, tune strengths |

**Takeaway:** ideamaxfx is lower-risk first adoption: wire grain/vignette/photocopy on background layers only, leave band photo frame untouched (no halftone).

## Recommendation: phased adoption

1. **Now — ideamaxfx (low risk):** Grain, vignette, photocopy on paper background; explicit ban on halftone for band photo frames (same as r5 structured rule).
2. **Later — PicTex (higher lift):** Replace PIL text layout for options B/C when we need deterministic reflow; keep OpenAI Art Director for style tokens, not coordinates.
3. **Keep:** `finalize_layout_spec` text dedup and `sanitize_band_photo_frame` regardless of renderer.

## Halftone policy (both stacks)

Never apply halftone to band photos in structured or compose paths — destroys face detail (documented in r5 Tuesday Jam feedback). ideamaxfx halftone is OK on backgrounds/textures only.
