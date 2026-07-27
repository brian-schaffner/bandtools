# Gig Flyers — next generation (staging-wild north star)

**Profile:** `GIG_FLYERS_PROFILE=staging-wild` on Band Tools staging.

## Goals

1. **Creative wild A/B/C** via Gemini full-canvas tiers without AI-yellow slop or fact typos.
2. **Assurance plane** — photo QA (incl. header gutter ghosts), gig-fact gate, post-render color correct + logo overlay.
3. **Flyer Agent** as primary UX — chat revise with **fact locks** on every wild round.
4. **Structured / shell** remain available under `prod-safe` profile for deterministic band-photo flyers.

## Shipped in this track

| Capability | Module / flag |
|------------|----------------|
| Profile bundle | `config/profiles.py`, `GIG_FLYERS_PROFILE=staging-wild` |
| Wild fact locks in prompts | `assurance/fact_locks.py`, `WILD_FACT_LOCKS=1` |
| Post-render yellow correction | `wild_design/color_correct.py`, `WILD_COLOR_CORRECT=1` |
| Wild enrich pipeline | `assurance/pipeline.py` (before logo overlay) |
| Gig-fact gate (wild review) | `assurance/facts.py`, `ASSURANCE_FACT_GATE=1` |
| Header gutter ghost detection | `detect_header_gutter_ghost` in `reference_compose.py` |
| Revision brief fact locks | `flyer_agent/revision_brief.py` + `agent_revise` |

## P0 backlog (next)

- Wild **hybrid typography** pass (background-only gen + deterministic fact text).
- Golden gig CI fixtures (Two Lane Tavern, Tuesday Jam).
- Venue address knowledge base beyond Stevie Ray’s rule.
- Multi-reference band convert (flagged).

## P1 backlog

- Unify bridge review into Flyer Agent views.
- Provider router + cost panel in agent UI.
- Prototype rank steering for wild round signatures (PR #11 patterns).

See [generation-modes.md](./generation-modes.md) for profile and env reference.
