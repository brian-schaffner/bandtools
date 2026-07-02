"""AI image prediction: style reference poster + band photo → predicted flyer."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from dotenv import load_dotenv

from evaluation_card import build_evaluation_card
from flyer_generator import gig_output_dir, resolve_gig_event
from gig_research import research_gig
from image_providers.errors import friendly_generation_error, is_retryable_429, retry_delay_seconds
from image_providers.reference_compose import (
    enforce_photo_bbox,
    parse_output_size,
    prepare_canvas_with_photo,
    validate_flyer_photo,
)
from output_paths import output_relative
from photo_selector import select_band_photo
from progress_helper import ProgressCallback, emit_progress
from text_validation import resolve_venue_address
from visual_constraints import (
    HATCH_CONSTRAINTS,
    StudyConstraints,
    get_constraints,
    hatch_predict_prompt_block,
)
from visual_studies import get_study

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# Photo placement tuned to Hatch stack (portrait between bar and mega name)
HATCH_PHOTO_PLACEMENT = {
    "width_frac": 0.52,
    "max_height_frac": 0.36,
    "y_center_frac": 0.46,
    "x_center_frac": 0.50,
    "angle": 0.0,
}


@dataclass(frozen=True)
class PredictResult:
    output_path: Path
    evaluation_card_path: Path
    manifest_path: Path
    provider: str
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "evaluation_card_path": str(self.evaluation_card_path),
            "manifest_path": str(self.manifest_path),
            "provider": self.provider,
            "dry_run": self.dry_run,
        }


def _prepare_hatch_canvas(
    band_photo_path: Path,
    output_size: tuple[int, int],
    work_dir: Path,
):
    """Place band photo on cream canvas using Hatch-study geometry."""
    from PIL import Image, ImageDraw

    from image_providers.reference_compose import (
        CANVAS_BACKGROUND,
        apply_photo_treatment,
        protection_zone,
    )

    placement = HATCH_PHOTO_PLACEMENT
    canvas_w, canvas_h = output_size
    photo = Image.open(band_photo_path).convert("RGBA")
    max_w = int(canvas_w * placement["width_frac"])
    max_h = int(canvas_h * placement["max_height_frac"])
    ratio = min(max_w / photo.width, max_h / photo.height)
    fitted = photo.resize(
        (max(1, int(photo.width * ratio)), max(1, int(photo.height * ratio))),
        Image.Resampling.LANCZOS,
    )
    fitted = apply_photo_treatment(fitted, "medium")

    cx = int(canvas_w * placement["x_center_frac"])
    cy = int(canvas_h * placement["y_center_frac"])
    x = max(0, min(cx - fitted.width // 2, canvas_w - fitted.width))
    y = max(0, min(cy - fitted.height // 2, canvas_h - fitted.height))
    photo_bbox = (x, y, x + fitted.width, y + fitted.height)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*CANVAS_BACKGROUND, 255))
    canvas.paste(fitted, (x, y), fitted)

    work_dir.mkdir(parents=True, exist_ok=True)
    canvas_path = work_dir / "hatch_compose_canvas.png"
    canvas.convert("RGB").save(canvas_path, format="PNG")

    protect_bbox = protection_zone(photo_bbox, (canvas_w, canvas_h))
    mask = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(mask)
    pl, pt, pr, pb = protect_bbox
    draw.rectangle([pl, pt, pr, pb], fill=(255, 255, 255, 255))
    mask_path = work_dir / "hatch_compose_mask.png"
    mask.save(mask_path, format="PNG")

    from image_providers.reference_compose import ComposeResult

    return ComposeResult(
        canvas_path=canvas_path,
        mask_path=mask_path,
        photo_bbox=photo_bbox,
        protection_bbox=protect_bbox,
        photo_layer=fitted.copy(),
        canvas_size=(canvas_w, canvas_h),
        tier="medium",
        reference_path=band_photo_path,
    )


def _gemini_api_key() -> str:
    return (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()


def _require_gemini_key() -> str:
    key = _gemini_api_key()
    if key:
        return key
    raise RuntimeError(
        "GOOGLE_API_KEY or GEMINI_API_KEY required for visual prediction. "
        "Add to gig-flyers/.env or Cloud Agent secrets, then re-run."
    )


def _gemini_predict(
    prompt: str,
    style_reference_path: Path,
    compose_canvas_path: Path,
    output_path: Path,
    *,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Call Gemini with style reference + composed band canvas."""
    from google import genai
    from google.genai import types

    api_key = _require_gemini_key()
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    aspect_ratio = os.getenv("GEMINI_IMAGE_ASPECT_RATIO", "2:3")
    client = genai.Client(api_key=api_key)

    style_bytes = style_reference_path.read_bytes()
    canvas_bytes = compose_canvas_path.read_bytes()

    contents: list[Any] = [
        prompt,
        types.Part.from_bytes(data=style_bytes, mime_type="image/jpeg"),
        "IMAGE 1 — STYLE REFERENCE: Match this poster's layout structure, hierarchy, and letterpress feel.",
        types.Part.from_bytes(data=canvas_bytes, mime_type="image/png"),
        "IMAGE 2 — INPUT CANVAS: Band photo is already placed. Add typography in cream areas only. "
        "Do NOT modify, redraw, duplicate, or frame the band photo.",
    ]

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
    )

    def _call():
        return client.models.generate_content(model=model, contents=contents, config=config)

    try:
        response = _call()
    except Exception as exc:
        if is_retryable_429(exc):
            delay = retry_delay_seconds(exc)
            emit_progress(
                on_progress,
                step="predict",
                substep="retry",
                message=f"Gemini rate limited, retrying in {int(delay)}s…",
                progress=50,
            )
            time.sleep(delay)
            response = _call()
        else:
            raise friendly_generation_error(exc, "gemini") from exc

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                if isinstance(data, str):
                    import base64

                    data = base64.b64decode(data)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(data)
                return

    raise RuntimeError("Gemini response contained no image data")


def predict_visual_flyer(
    gig_id: str,
    *,
    study_id: str = HATCH_CONSTRAINTS.study_id,
    round_num: int = 1,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
    predict_fn: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Generate flyer via AI image prediction guided by a real poster reference."""
    event = resolve_gig_event(gig_id)
    band = os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    study = get_study(study_id)
    constraints = get_constraints(study_id)
    if study is None or constraints is None:
        raise ValueError(f"Unknown or unconstrained study: {study_id}")

    emit_progress(on_progress, step="research", message="Researching gig…", progress=5)
    research = research_gig(event, on_progress=on_progress)

    emit_progress(on_progress, step="photo", message="Selecting band photo…", progress=15)
    selected = select_band_photo(event, research, on_progress=on_progress)
    band_photo = ROOT / selected["path"] if selected and selected.get("path") else None

    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    address = resolve_venue_address(event)

    prompt = hatch_predict_prompt_block(
        venue=event.venue,
        date=date_str,
        time=time_str,
        band=band,
        address=address,
    )

    style_ref = Path(study.image_path)
    if not style_ref.is_file():
        raise FileNotFoundError(f"Study reference image missing: {style_ref}")

    out_dir = gig_output_dir(event) / "visual_predict"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"predict_r{round_num}.png"
    card_path = out_dir / f"evaluation_r{round_num}.png"
    manifest_path = out_dir / f"manifest_r{round_num}.json"

    provider = "gemini"
    compose = None

    if dry_run:
        out_path.write_bytes(b"")
        card_path.write_bytes(b"")
    else:
        if band_photo is None or not band_photo.is_file():
            raise RuntimeError("Band photo required for visual prediction")

        size = parse_output_size(os.getenv("OPENAI_IMAGE_SIZE", "1024x1536"))
        with tempfile.TemporaryDirectory(prefix="gigflyers-predict-") as tmp:
            compose = _prepare_hatch_canvas(band_photo, size, Path(tmp))
            emit_progress(
                on_progress,
                step="predict",
                message="Calling AI to predict flyer from style reference…",
                progress=40,
            )
            fn = predict_fn or _gemini_predict
            fn(prompt, style_ref, compose.canvas_path, out_path, on_progress=on_progress)

        if compose is not None:
            enforce_photo_bbox(out_path, compose, force=True)
            validation = validate_flyer_photo(out_path, band_photo, compose)
            if not validation.passed:
                failed = [c for c in validation.checks if not c.get("passed")]
                detail = "; ".join(f"{c.get('name')}: {c.get('detail')}" for c in failed[:3])
                raise RuntimeError(f"Photo validation failed after prediction — {detail}")

    extra_lines = [
        "AI path: no layout constraint auto-check",
        "Review visually against reference panel",
        f"Study: {study.title}",
    ]
    build_evaluation_card(
        reference_path=style_ref,
        generated_path=out_path if out_path.stat().st_size > 0 else style_ref,
        output_path=card_path,
        study_title=study.title,
        method="AI image prediction (Gemini + style ref)",
        constraint_report=None,
        extra_checklist_lines=extra_lines,
    )

    manifest = {
        "gig_id": gig_id,
        "round": round_num,
        "study_id": study_id,
        "method": "ai_visual_predict",
        "provider": provider,
        "path_rel": output_relative(out_path),
        "evaluation_card_rel": output_relative(card_path),
        "style_reference": study.source_url,
        "prompt": prompt,
        "research_venue_type": research.get("venue_type"),
        "dry_run": dry_run,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    emit_progress(on_progress, step="done", message="Visual prediction complete", progress=100)
    return manifest
