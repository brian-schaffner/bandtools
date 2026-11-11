"""Generate a flyer by showing the model a real reference poster + band photo + logo."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from evaluation_card import build_evaluation_card
from gig_calendar import GigEvent
from output_paths import get_output_dir, output_relative
from structured_layout.band_mark import find_band_logo
from visual_studies import STUDY_CACHE, VisualStudy, get_study

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

HATCH_REF = STUDY_CACHE / "hank_hatch.jpg"
ALTAMONT_REF = STUDY_CACHE / "altamont2.jpg"
WOODSTOCK_REF = STUDY_CACHE / "woodstock2.jpg"
if not WOODSTOCK_REF.is_file():
    WOODSTOCK_REF = STUDY_CACHE / "woodstock_thumb.jpg"
DEFAULT_PHOTO = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"
OUT_DIR = get_output_dir() / "reference_study"

REF_BY_STUDY: dict[str, Path] = {
    "hatch_hank_williams_1953": HATCH_REF,
    "altamont_free_concert_1969": ALTAMONT_REF,
    "woodstock_festival_1969": WOODSTOCK_REF,
}

DEFAULT_STUDY_ID = "hatch_hank_williams_1953"

PROTECTED_ASSET_STUDIES = frozenset({"woodstock_festival_1969", "altamont_free_concert_1969"})


def _paper_for_study(study_id: str) -> tuple[int, int, int]:
    if study_id == "woodstock_festival_1969":
        return (211, 47, 47)
    return (242, 235, 220)


def _label_fill_for_study(study_id: str) -> tuple[int, int, int]:
    if study_id == "woodstock_festival_1969":
        return (255, 255, 255)
    return (20, 20, 20)


def resolve_study_logo(band: str, study_id: str) -> Path:
    paper = _paper_for_study(study_id)
    logo = find_band_logo(band, paper=paper)
    if logo is not None and logo.is_file():
        return logo
    name = "lindsey-lane-band-light.png" if sum(paper) / 3 < 128 else "lindsey-lane-band-dark.png"
    return ROOT / "assets/logos" / name


def _event_facts_block(
    *,
    venue: str,
    date: str,
    time: str,
    band: str,
    address: str = "",
) -> str:
    lines = [
        "EVENT FACTS (copy exactly):",
        f"  Band / headliner: {band}",
        f"  Venue: {venue}",
        f"  Date: {date}",
        f"  Time: {time}",
    ]
    if address:
        lines.append(f"  Address: {address}")
    return "\n".join(lines)


def build_hatch_prompt(*, venue: str, date: str, time: str, band: str, address: str = "") -> str:
    return (
        "You are designing a letterpress-style country gig poster.\n\n"
        "You will receive THREE images:\n"
        "  IMAGE 1 — STYLE REFERENCE: a real 1953 Hatch Show Print poster (Hank Williams). "
        "Match its layout structure, hierarchy, and red/black/cream letterpress feel.\n"
        "  IMAGE 2 — BAND PHOTO: use this exact photo as the centered portrait. "
        "Do not redraw, duplicate, or distort the musicians.\n"
        "  IMAGE 3 — BAND LOGO: place this lockup near the band name or bottom hero type. "
        "Do not alter the logo artwork.\n\n"
        "Create ONE finished vertical flyer (2:3 aspect).\n"
        "Stack top→bottom like the reference: venue, date, presenter bar, portrait, mega band name.\n"
        "Use only cream paper + red + black ink. No gradients, no extra colors.\n\n"
        f"{_event_facts_block(venue=venue, date=date, time=time, band=band, address=address)}\n\n"
        "Output a single complete flyer image only."
    )


def build_altamont_prompt(*, venue: str, date: str, time: str, band: str, address: str = "") -> str:
    return (
        "You are designing a gritty 1969-style rock club / festival bill poster.\n\n"
        "You will receive a canvas with assets already placed:\n"
        "  STYLE REFERENCE at top — match its asymmetric layout and red/black screen-print feel.\n"
        "  BAND PHOTO — already pasted lower-left. Preserve EXACTLY — do not redraw or repaint.\n"
        "  BAND LOGO — already pasted. Must remain visible; do not replace with plain type.\n\n"
        "Layout (like reference):\n"
        "  • Headliner name largest at top\n"
        "  • Promo hook line (e.g. LIVE AT / ONE NIGHT ONLY) in red caps with star accents\n"
        "  • Date line (black) then venue line (red) — alternate colors by line\n"
        "  • RIGHT SIDEBAR column: SPECIAL GUESTS / LOCAL OPENERS (not a bottom list)\n"
        "  • Show time in footer\n"
        "Palette: cream + red + black only.\n\n"
        f"{_event_facts_block(venue=venue, date=date, time=time, band=band, address=address)}\n\n"
        "Output one complete vertical flyer."
    )


def build_woodstock_prompt(*, venue: str, date: str, time: str, band: str, address: str = "") -> str:
    return (
        "You are designing a psychedelic 1969 festival poster — graphically complex.\n\n"
        "You will receive a canvas with assets already placed:\n"
        "  STYLE REFERENCE at top — transform this zone into original hero art (dove/guitar "
        "motif inspired by Woodstock, not a copy).\n"
        "  BAND PHOTO — already pasted in the footer. Preserve it EXACTLY: same faces, poses, "
        "and framing. Do not redraw, repaint, halftone again, duplicate, or cover the musicians.\n"
        "  BAND LOGO — already pasted in the footer. Must stay clearly visible at readable size. "
        "Do not replace the logo with plain type or omit it.\n\n"
        "Add around the protected assets:\n"
        "  - Solid red field behind hero art\n"
        "  - Large festival hook slogan in hand-drawn yellow lettering\n"
        "  - THREE-COLUMN footer grid: lineup | logistics/dates | headliner block\n"
        "  - Flat 4-color palette: red, yellow, blue, black, white — no gradients\n\n"
        "Hierarchy: slogan + symbolic art dominate; band logo + name remain legible in footer.\n"
        "Include dense but readable small type in footer columns.\n\n"
        f"{_event_facts_block(venue=venue, date=date, time=time, band=band, address=address)}\n\n"
        "Festival hook suggestion: ONE NIGHT OF BLUES & ROCK (adapt to event).\n"
        "Output one complete vertical festival poster."
    )


STUDY_PROMPT_BUILDERS = {
    "hatch_hank_williams_1953": build_hatch_prompt,
    "altamont_free_concert_1969": build_altamont_prompt,
    "woodstock_festival_1969": build_woodstock_prompt,
}


def build_generation_prompt(
    *,
    study_id: str,
    venue: str,
    date: str,
    time: str,
    band: str,
    address: str = "",
) -> str:
    builder = STUDY_PROMPT_BUILDERS.get(study_id, build_hatch_prompt)
    return builder(venue=venue, date=date, time=time, band=band, address=address)


def _collage_edit_preamble(study_id: str) -> str:
    if study_id == "woodstock_festival_1969":
        return (
            "The canvas already contains a style reference at top, plus a band photo and band logo "
            "in the footer. Those photo and logo regions are LOCKED — do not move, redraw, replace, "
            "or cover them. Build hero art, slogan, and footer typography around the locked assets. "
            "Remove any briefing labels. Match Woodstock complexity: hero art, slogan, 3-column footer, "
            "flat 4-color palette.\n\n"
        )
    if study_id == "altamont_free_concert_1969":
        return (
            "The canvas already contains a style reference at top, plus a band photo and band logo. "
            "Photo and logo regions are LOCKED — do not redraw or replace them. Add typography and "
            "layout around the locked assets. Match asymmetric layout, red/black alternation, sidebar "
            "guest column.\n\n"
        )
    return (
        "The input image is a briefing sheet. STYLE REFERENCE at top shows the target layout. "
        "BAND PHOTO and BAND LOGO are assets to include exactly. "
        "Render ONE finished vertical letterpress gig flyer in the outlined area at bottom, "
        "then expand to fill the entire canvas as a single cohesive poster. "
        "Remove briefing labels and boxes. Match the reference hierarchy and palette.\n\n"
    )


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_collage_input(
    *,
    reference_path: Path,
    photo_path: Path,
    logo_path: Path,
    out_path: Path,
    size: tuple[int, int] = (1024, 1536),
    study_id: str = "hatch_hank_williams_1953",
) -> Path:
    """Single-sheet fallback for APIs that accept one image: ref + assets + blank render zone."""
    w, h = size
    paper = _paper_for_study(study_id)
    sheet = Image.new("RGB", size, paper)
    draw = ImageDraw.Draw(sheet)
    label = _load_font(18)
    label_fill = _label_fill_for_study(study_id)
    ref_label_fill = (255, 220, 220) if study_id == "woodstock_festival_1969" else (80, 20, 20)

    ref_h = int(h * (0.42 if study_id == "woodstock_festival_1969" else 0.38))
    ref = Image.open(reference_path).convert("RGB")
    ref_fit = _fit(ref, w - 48, ref_h - 36)
    sheet.paste(ref_fit, ((w - ref_fit.width) // 2, 24))
    draw.text((24, 4), "STYLE REFERENCE (match this layout)", fill=ref_label_fill, font=label)

    assets_y = ref_h + 12
    photo = Image.open(photo_path).convert("RGB")
    photo_fit = _fit(photo, int(w * 0.42), int(h * 0.22))
    sheet.paste(photo_fit, (24, assets_y))
    draw.text((24, assets_y - 20), "BAND PHOTO (use exactly)", fill=label_fill, font=label)

    logo = Image.open(logo_path).convert("RGBA")
    logo_fit = _fit(logo, int(w * 0.35), int(h * 0.12))
    lx = w - logo_fit.width - 24
    sheet.paste(logo_fit, (lx, assets_y), logo_fit if logo_fit.mode == "RGBA" else None)
    draw.text((lx, assets_y - 20), "BAND LOGO (include exactly)", fill=label_fill, font=label)

    render_y = assets_y + int(h * 0.24)
    draw.rectangle([24, render_y, w - 24, h - 24], outline=(179, 27, 27), width=3)
    draw.text(
        (36, render_y + 12),
        "RENDER FINAL FLYER HERE\n(single poster, same style as reference)",
        fill=(100, 100, 100),
        font=label,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG")
    return out_path


def _fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    ratio = min(max_w / img.width, max_h / img.height)
    nw = max(1, int(img.width * ratio))
    nh = max(1, int(img.height * ratio))
    out = img.resize((nw, nh), Image.Resampling.LANCZOS)
    if img.mode == "RGBA":
        return out
    return out.convert("RGB")


def _prepare_study_photo(photo_path: Path, study_id: str) -> Image.Image:
    """PIL-only photo treatment — never ask the model to redraw faces."""
    photo = Image.open(photo_path).convert("RGBA")
    if study_id == "woodstock_festival_1969":
        from structured_layout.graphic_primitives import duotone_photo

        return duotone_photo(photo, (17, 17, 17), (245, 196, 0))
    if study_id == "altamont_free_concert_1969":
        from structured_layout.graphic_primitives import threshold_photo

        return threshold_photo(photo)
    return photo


def build_protected_study_canvas(
    *,
    reference_path: Path,
    photo_path: Path,
    logo_path: Path,
    out_dir: Path,
    study_id: str,
    size: tuple[int, int] = (1024, 1536),
) -> tuple[Path, Path, tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Pre-paste band photo + logo on canvas; return paths and bboxes for mask protection."""
    w, h = size
    paper = _paper_for_study(study_id)
    canvas = Image.new("RGB", size, paper)

    ref_h = int(h * 0.36)
    ref = Image.open(reference_path).convert("RGB")
    ref_fit = _fit(ref, w - 48, ref_h)
    canvas.paste(ref_fit, ((w - ref_fit.width) // 2, 16))

    photo_layer = _prepare_study_photo(photo_path, study_id)
    photo_fit = _fit(photo_layer, int(w * 0.44), int(h * 0.24))
    px, py = 36, int(h * 0.56)
    canvas.paste(photo_fit, (px, py), photo_fit if photo_fit.mode == "RGBA" else None)
    photo_bbox = (px, py, px + photo_fit.width, py + photo_fit.height)

    logo = Image.open(logo_path).convert("RGBA")
    logo_fit = _fit(logo, int(w * 0.46), int(h * 0.13))
    lx = w - logo_fit.width - 36
    ly = int(h * 0.74)
    canvas.paste(logo_fit, (lx, ly), logo_fit)
    logo_bbox = (lx, ly, lx + logo_fit.width, ly + logo_fit.height)

    out_dir.mkdir(parents=True, exist_ok=True)
    canvas_path = out_dir / "compose_canvas.png"
    canvas.save(canvas_path, format="PNG")

    mask = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(mask)
    pad = 28
    for left, top, right, bottom in (photo_bbox, logo_bbox):
        draw.rectangle(
            [left - pad, top - pad, right + pad, bottom + pad],
            fill=(255, 255, 255, 255),
        )
    mask_path = out_dir / "compose_mask.png"
    mask.save(mask_path, format="PNG")
    return canvas_path, mask_path, photo_bbox, logo_bbox


def _uses_protected_assets(study_id: str) -> bool:
    if study_id in PROTECTED_ASSET_STUDIES:
        return True
    return os.getenv("REFERENCE_STUDY_PROTECTED_ASSETS", "").strip().lower() in {"1", "true", "yes"}


def generate_openai_multiref(
    prompt: str,
    *,
    reference_path: Path,
    photo_path: Path,
    logo_path: Path,
    output_path: Path,
    study_id: str = DEFAULT_STUDY_ID,
) -> None:
    """OpenAI: collage input sheet + images.edit to render final flyer."""
    from openai import OpenAI

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    size = os.getenv("OPENAI_IMAGE_SIZE", "1024x1536")
    quality = os.getenv("OPENAI_IMAGE_QUALITY", "high")

    with tempfile.TemporaryDirectory(prefix="ref-study-") as tmp:
        tmp_path = Path(tmp)
        edit_prompt = f"{_collage_edit_preamble(study_id)}{prompt}"
        if _uses_protected_assets(study_id):
            canvas_path, mask_path, _, _ = build_protected_study_canvas(
                reference_path=reference_path,
                photo_path=photo_path,
                logo_path=logo_path,
                out_dir=tmp_path,
                study_id=study_id,
            )
            with canvas_path.open("rb") as image_f, mask_path.open("rb") as mask_f:
                response = client.images.edit(
                    model=model,
                    image=image_f,
                    mask=mask_f,
                    prompt=edit_prompt,
                    size=size,
                    quality=quality,
                    input_fidelity="high",
                    n=1,
                )
        else:
            collage = tmp_path / "input_sheet.png"
            build_collage_input(
                reference_path=reference_path,
                photo_path=photo_path,
                logo_path=logo_path,
                out_path=collage,
                study_id=study_id,
            )
            with collage.open("rb") as f:
                response = client.images.edit(
                    model=model,
                    image=f,
                    prompt=edit_prompt,
                    size=size,
                    quality=quality,
                    input_fidelity="high",
                    n=1,
                )
        item = response.data[0]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if item.b64_json:
            output_path.write_bytes(base64.b64decode(item.b64_json))
        elif item.url:
            import urllib.request

            with urllib.request.urlopen(item.url, timeout=120) as resp:
                output_path.write_bytes(resp.read())
        else:
            raise RuntimeError("OpenAI returned no image data")


def generate_gemini_multiref(
    prompt: str,
    *,
    reference_path: Path,
    photo_path: Path,
    logo_path: Path,
    output_path: Path,
) -> None:
    """Gemini: native multi-image input (best fit for this task)."""
    from google import genai
    from google.genai import types

    api_key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY required")

    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    aspect = os.getenv("GEMINI_IMAGE_ASPECT_RATIO", "2:3")

    contents: list[Any] = [
        prompt,
        types.Part.from_bytes(data=reference_path.read_bytes(), mime_type="image/jpeg"),
        "IMAGE 1 — STYLE REFERENCE POSTER",
        types.Part.from_bytes(data=photo_path.read_bytes(), mime_type="image/jpeg"),
        "IMAGE 2 — BAND PHOTO (use exactly, centered portrait)",
        types.Part.from_bytes(data=logo_path.read_bytes(), mime_type="image/png"),
        "IMAGE 3 — BAND LOGO (include near band name)",
    ]
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=aspect),
    )
    response = client.models.generate_content(model=model, contents=contents, config=config)
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                if isinstance(data, str):
                    data = base64.b64decode(data)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(data)
                return
    raise RuntimeError("Gemini returned no image")


def generate_reference_study_flyer(
    event: GigEvent,
    *,
    study_id: str = DEFAULT_STUDY_ID,
    band: str = "Lindsey Lane Band",
    photo_path: Path | None = None,
    logo_path: Path | None = None,
    reference_path: Path | None = None,
    provider: str | None = None,
    generator: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Show reference poster + photo + logo; generate similar flyer for gig."""
    ref = reference_path or REF_BY_STUDY.get(study_id, HATCH_REF)
    photo = photo_path or DEFAULT_PHOTO
    logo = logo_path or resolve_study_logo(band, study_id)
    for label, path in [("reference", ref), ("photo", photo), ("logo", logo)]:
        if not path.is_file():
            raise FileNotFoundError(f"Missing {label}: {path}")

    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    prompt = build_generation_prompt(
        study_id=study_id,
        venue=event.venue,
        date=date_str,
        time=time_str,
        band=band,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{event.gig_id}_{study_id}"
    out_path = OUT_DIR / f"{stem}_reference_gen.png"
    card_path = OUT_DIR / f"{stem}_reference_eval.png"
    sheet_path = OUT_DIR / f"{stem}_input_sheet.png"
    build_collage_input(
        reference_path=ref,
        photo_path=photo,
        logo_path=logo,
        out_path=sheet_path,
        study_id=study_id,
    )

    chosen = (provider or os.getenv("REFERENCE_STUDY_PROVIDER") or "openai").strip().lower()
    if generator:
        generator(prompt, reference_path=ref, photo_path=photo, logo_path=logo, output_path=out_path)
        used = "custom"
    elif chosen == "gemini":
        generate_gemini_multiref(
            prompt, reference_path=ref, photo_path=photo, logo_path=logo, output_path=out_path
        )
        used = "gemini"
    else:
        generate_openai_multiref(
            prompt,
            reference_path=ref,
            photo_path=photo,
            logo_path=logo,
            output_path=out_path,
            study_id=study_id,
        )
        used = "openai"

    study = get_study(study_id)
    ref_label = {
        "hatch_hank_williams_1953": "Hank Williams reference",
        "altamont_free_concert_1969": "Altamont reference",
        "woodstock_festival_1969": "Woodstock reference",
    }.get(study_id, "Style reference")
    build_evaluation_card(
        reference_path=ref,
        generated_path=out_path,
        output_path=card_path,
        study_title=study.title if study else ref_label,
        method=f"Reference study generate ({used})",
        panel_labels=(ref_label, "AI generated flyer", "Brief"),
        extra_checklist_lines=[
            "Inputs: reference poster + band photo + logo",
            f"Study: {study_id}",
            f"Provider: {used}",
            "Photo/logo: PIL pre-paste + mask (protected)" if _uses_protected_assets(study_id) else "Photo/logo: briefing sheet only",
            f"Venue: {event.venue}",
            f"Date: {date_str}",
        ],
    )

    manifest = {
        "gig_id": event.gig_id,
        "study_id": study_id,
        "provider": used,
        "reference": str(ref),
        "photo": str(photo),
        "logo": str(logo),
        "input_sheet_rel": output_relative(sheet_path),
        "path_rel": output_relative(out_path),
        "evaluation_card_rel": output_relative(card_path),
        "prompt": prompt,
    }
    manifest_path = OUT_DIR / f"{stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
