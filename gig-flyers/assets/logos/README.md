# Band logos (Option C + optional B)

Official Lindsey Lane Band nested-L lockup. Replace these PNGs with your
master files (transparent background recommended):

| File | Use |
|------|-----|
| `lindsey-lane-band-dark.png` | Dark ink on transparent — light/paper flyers |
| `lindsey-lane-band-light.png` | Light ink on transparent — dark/neon flyers |
| `lindsey-lane-band-on-black.png` | White lockup on black rectangle |
| `lindsey-lane-band-on-white.png` | Black lockup on white rectangle |

`find_band_logo()` picks light vs dark automatically from flyer background.

Regenerate approximations from the lockup script:

```bash
python3 scripts/render_band_logo_assets.py
```

Other bands: add `{band-slug}-dark.png` and `{band-slug}-light.png`.
