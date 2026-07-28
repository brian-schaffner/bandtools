# Lindsey Lane Band logos

## Source files

Official uploads live in [`../logos/`](../logos/) (2026 stack + circle). Processed PNGs for the app are in this directory.

```bash
cd gig-flyers && python3 scripts/install_band_logos.py
```

| Output | Use |
|--------|-----|
| `lindsey-lane-band-dark.png` | Dark ink, transparent — light/paper flyers |
| `lindsey-lane-band-light.png` | Light ink, transparent — dark/neon flyers |
| `lindsey-lane-band-circle.png` | Circular badge — corner placement when `FLY_LOGO_PLACEMENT=corner` |
| `lindsey-lane-band-on-white.png` / `-on-black.png` | Full lockups with background |

Wild flyers use **large footer/top lockups** (`wild_design/logo_placement.py`). `find_band_logo()` picks light vs dark from background luminance.

Legacy fallback: repo-root `IMG_8015.png` / `IMG_8016.png` if `logos/` uploads are missing.
