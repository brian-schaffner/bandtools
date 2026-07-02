Official Lindsey Lane Band nested-L lockup from `IMG_8016.png` (dark/transparent)
and `IMG_8015.png` (on white) at the **repo root**.

Re-install after updating root uploads:

```bash
python3 scripts/install_band_logos.py
```

| File | Source | Use |
|------|--------|-----|
| `lindsey-lane-band-dark.png` | IMG_8016 | Dark ink, transparent — light/paper flyers |
| `lindsey-lane-band-light.png` | derived | Light ink, transparent — dark/neon flyers |
| `lindsey-lane-band-on-white.png` | IMG_8015 | Full lockup on white |
| `lindsey-lane-band-on-black.png` | derived | Full lockup on black |

`find_band_logo()` picks light vs dark from flyer background automatically.

Other bands: add `{band-slug}-dark.png` and `{band-slug}-light.png`.
