# Lindsey Lane Band logos

## New lockup (stack + brush stroke)

Place source PNGs in [`source/`](source/) (see `source/README.md`), then:

```bash
cd gig-flyers && python3 scripts/install_band_logos.py
```

| Output | Use |
|--------|-----|
| `lindsey-lane-band-dark.png` | Dark ink, transparent — light/paper flyers |
| `lindsey-lane-band-light.png` | Light ink, transparent — dark/neon flyers |
| `lindsey-lane-band-circle.png` | Circular badge — **wild poster top-right overlay** |
| `lindsey-lane-band-on-white.png` | Full lockup on white |
| `lindsey-lane-band-on-black.png` | Full lockup on black |

`find_band_logo()` picks light vs dark from flyer background. Badge overlay prefers `-circle.png` when present.

## Legacy

Nested-L lockup from repo-root `IMG_8015.png` / `IMG_8016.png` if `source/` stack files are missing.

Docker build runs `install_band_logos.py` first, then falls back to procedural `render_band_logo_assets.py`.
