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
from visual_constraints import hatch_predict_prompt_block
from visual_studies import STUDY_CACHE, get_study

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

HATCH_REF = STUDY_CACHE / "hank_hatch.jpg"
DEFAULT_PHOTO = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"
OUT_DIR = get_output_dir() / "reference_study"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_generation_prompt(
    *,
    venue: str,
    date: str,
    time: str,
    band: str,
    address: str = "",
) -> str:
    """Prompt when the model can see separate reference, photo, and logo images."""
    facts = hatch_predict_prompt_block(
        venue=venue, date=date, time=time, band=band, address=address
    )
    return (
        "You are designing a letterpress-style country gig poster.\n\n"
        "You will receive THREE images:\n"
        "  IMAGE 1 — STYLE REFERENCE: a real 1953 Hatch Show Print poster (Hank Williams). "
        "Match its layout structure, hierarchy, and red/black/cream letterpress feel.\n"
        "  IMAGE 2 — BAND PHOTO: use this exact photo as the centered portrait. "
        "Do not redraw, duplicate, or distort the musicians.\n"
        "  IMAGE 3 — BAND LOGO: place this lockup near the band name or bottom hero type. "
        "Do not alter the logo artwork.\n\n"
        "Create ONE finished vertical flyer (2:3 aspect) for the event below.\n"
        "Stack top→bottom like the reference: venue, date, presenter bar, portrait, mega band name.\n"
        "Use only cream paper + red + black ink. No gradients, no extra colors.\n\n"
        f"{facts}\n\n"
        "Output a single complete flyer image only."
    )


def build_collage_input(
    *,
    reference_path: Path,
    photo_path: Path,
    logo_path: Path,
    out_path: Path,
    size: tuple[int, int] = (1024, 1536),
) -> Path:
    """Single-sheet fallback for APIs that accept one image: ref + assets + blank render zone."""
    w, h = size
    sheet = Image.new("RGB", size, (242, 235, 220))
    draw = ImageDraw.Draw(sheet)
    label = _load_font(18)

    ref_h = int(h * 0.38)
    ref = Image.open(reference_path).convert("RGB")
    ref_fit = _fit(ref, w - 48, ref_h - 36)
    sheet.paste(ref_fit, ((w - ref_fit.width) // 2, 24))
    draw.text((24, 4), "STYLE REFERENCE (match this layout)", fill=(80, 20, 20), font=label)

    assets_y = ref_h + 12
    photo = Image.open(photo_path).convert("RGB")
    photo_fit = _fit(photo, int(w * 0.42), int(h * 0.22))
    sheet.paste(photo_fit, (24, assets_y))
    draw.text((24, assets_y - 20), "BAND PHOTO (use exactly)", fill=(20, 20, 20), font=label)

    logo = Image.open(logo_path).convert("RGBA")
    logo_fit = _fit(logo, int(w * 0.35), int(h * 0.12))
    lx = w - logo_fit.width - 24
    sheet.paste(logo_fit, (lx, assets_y), logo_fit if logo_fit.mode == "RGBA" else None)
    draw.text((lx, assets_y - 20), "BAND LOGO (include)", fill=(20, 20, 20), font=label)

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


def generate_openai_multiref(
    prompt: str,
    *,
    reference_path: Path,
    photo_path: Path,
    logo_path: Path,
    output_path: Path,
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
        collage = Path(tmp) / "input_sheet.png"
        build_collage_input(
            reference_path=reference_path,
            photo_path=photo_path,
            logo_path=logo_path,
            out_path=collage,
        )
        edit_prompt = (
            "The input image is a briefing sheet. STYLE REFERENCE at top shows the target layout. "
            "BAND PHOTO and BAND LOGO are assets to include exactly. "
            "Render ONE finished vertical letterpress gig flyer in the outlined area at bottom, "
            "then expand to fill the entire canvas as a single cohesive poster. "
            "Remove briefing labels and boxes. Match the reference hierarchy and palette.\n\n"
            f"{prompt}"
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
    band: str = "Lindsey Lane Band",
    photo_path: Path | None = None,
    logo_path: Path | None = None,
    reference_path: Path | None = None,
    provider: str | None = None,
    generator: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Show reference poster + photo + logo; generate similar flyer for gig."""
    ref = reference_path or HATCH_REF
    photo = photo_path or DEFAULT_PHOTO
    logo = logo_path or find_band_logo(band, paper=(242, 235, 220))
    if logo is None or not logo.is_file():
        logo = ROOT / "assets/logos/lindsey-lane-band-dark.png"
    for label, path in [("reference", ref), ("photo", photo), ("logo", logo)]:
        if not path.is_file():
            raise FileNotFoundError(f"Missing {label}: {path}")

    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    prompt = build_generation_prompt(
        venue=event.venue,
        date=date_str,
        time=time_str,
        band=band,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{event.gig_id}_reference_gen.png"
    card_path = OUT_DIR / f"{event.gig_id}_reference_eval.png"
    sheet_path = OUT_DIR / f"{event.gig_id}_input_sheet.png"
    build_collage_input(
        reference_path=ref,
        photo_path=photo,
        logo_path=logo,
        out_path=sheet_path,
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
            prompt, reference_path=ref, photo_path=photo, logo_path=logo, output_path=out_path
        )
        used = "openai"

    study = get_study("hatch_hank_williams_1953")
    build_evaluation_card(
        reference_path=ref,
        generated_path=out_path,
        output_path=card_path,
        study_title=study.title if study else "Hatch reference",
        method=f"Reference study generate ({used})",
        panel_labels=("Hank Williams reference", "AI generated flyer", "Brief"),
        extra_checklist_lines=[
            "Inputs: reference poster + band photo + logo",
            f"Provider: {used}",
            f"Venue: {event.venue}",
            f"Date: {date_str}",
        ],
    )

    manifest = {
        "gig_id": event.gig_id,
        "provider": used,
        "reference": str(ref),
        "photo": str(photo),
        "logo": str(logo),
        "input_sheet_rel": output_relative(sheet_path),
        "path_rel": output_relative(out_path),
        "evaluation_card_rel": output_relative(card_path),
        "prompt": prompt,
    }
    manifest_path = OUT_DIR / f"{event.gig_id}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
