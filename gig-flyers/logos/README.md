# Lindsey Lane Band — official logo uploads (2026)

These PNGs are the **source of truth** for flyer overlays. The installer copies processed versions into `assets/logos/`.

| File | Use in installer |
|------|------------------|
| `Lindset Lane Band Logo 2026 - Black and Transparent.png` | Dark ink lockup (transparent) → light/paper flyers |
| `Lindsey Lane Band New Logo 2026.png` | White on black (red brush) → dark flyers |
| `Lindsey Lane Logo for FB Profile Picture.png` | Circular badge (optional corner / badge variant) |
| `Lindsey Lane Band New Logo 2026.svg` | Master vector (not used at runtime) |

After adding or replacing files:

```bash
cd gig-flyers && python3 scripts/install_band_logos.py
```

Docker/staging runs the same script at image build time.
