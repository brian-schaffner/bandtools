"""AI image prediction: style reference poster + band photo → predicted flyer."""

from __future__ import annotations

import base64
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
from image_providers.errors import ImageGenerationError, friendly_generation_error, is_quota_error, is_retryable_429, retry_delay_seconds
from image_providers.reference_compose import (
    ComposeResult,
    enforce_photo_bbox,
    parse_output_size,
    validate_flyer_photo,
)
from output_paths import output_relative
from photo_selector import select_band_photo
from progress_helper import ProgressCallback, emit_progress
from text_validation import resolve_venue_address
from visual_constraints import (
    HATCH_CONSTRAINTS,
    get_constraints,
    hatch_predict_prompt_block,
)
from visual_studies import get_study

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

HATCH_PHOTO_PLACEMENT = {
    "width_frac": 0.52,
    "max_height_frac": 0.36,
    "y_center_frac": 0.46,
    "x_center_frac": 0.50,
    "angle": 0.0,
}


def _prepare_hatch_canvas(
    band_photo_path: Path,
    output_size: tuple[int, int],
    work_dir: Path,
) -> ComposeResult:
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


def _openai_api_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def _resolve_predict_provider() -> str:
    return (os.getenv("VISUAL_PREDICT_PROVIDER") or "auto").strip().lower()


def _predict_api_available(provider: str) -> bool:
    if provider == "openai":
        return bool(_openai_api_key())
    return bool(_gemini_api_key())


def _gemini_predict(
    prompt: str,
    style_reference_path: Path,
    compose: ComposeResult,
    output_path: Path,
    *,
    on_progress: ProgressCallback | None = None,
) -> None:
    from google import genai
    from google.genai import types

    api_key = _gemini_api_key()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY required for Gemini visual prediction")

    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    aspect_ratio = os.getenv("GEMINI_IMAGE_ASPECT_RATIO", "2:3")
    client = genai.Client(api_key=api_key)

    contents: list[Any] = [
        prompt,
        types.Part.from_bytes(data=style_reference_path.read_bytes(), mime_type="image/jpeg"),
        "IMAGE 1 — STYLE REFERENCE: Match this poster's layout structure, hierarchy, and letterpress feel.",
        types.Part.from_bytes(data=compose.canvas_path.read_bytes(), mime_type="image/png"),
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

    raise RuntimeError("Gemini response contained no image data")


def _openai_predict(
    prompt: str,
    style_reference_path: Path,
    compose: ComposeResult,
    output_path: Path,
    *,
    on_progress: ProgressCallback | None = None,
) -> None:
    from openai import OpenAI

    from image_providers.openai import REFERENCE_EDIT_PROMPT_PREFIX

    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required for OpenAI visual prediction")

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    size = os.getenv("OPENAI_IMAGE_SIZE", "1024x1536")
    quality = os.getenv("OPENAI_IMAGE_QUALITY", "medium")

    style_note = (
        f"STYLE REFERENCE (not in image — follow this layout): 1953 Hatch Show Print letterpress poster. "
        f"Reference file: {style_reference_path.name}. "
    )
    edit_prompt = f"{REFERENCE_EDIT_PROMPT_PREFIX}\n{style_note}\n{prompt}"

    emit_progress(
        on_progress,
        step="predict",
        substep="openai",
        message="Calling OpenAI images.edit for Hatch-style typography…",
        progress=45,
    )

    with compose.canvas_path.open("rb") as image_file:
        kwargs: dict[str, Any] = {
            "model": model,
            "image": image_file,
            "prompt": edit_prompt,
            "size": size,
            "quality": quality,
            "input_fidelity": "high",
            "n": 1,
        }
        if compose.mask_path and compose.mask_path.is_file():
            with compose.mask_path.open("rb") as mask_file:
                kwargs["mask"] = mask_file
                response = client.images.edit(**kwargs)
        else:
            response = client.images.edit(**kwargs)

    item = response.data[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if item.b64_json:
        output_path.write_bytes(base64.b64decode(item.b64_json))
    elif item.url:
        import urllib.request

        with urllib.request.urlopen(item.url, timeout=120) as resp:
            output_path.write_bytes(resp.read())
    else:
        raise RuntimeError("OpenAI image response had no b64_json or url")


def _run_predict(
    provider: str,
    prompt: str,
    style_reference_path: Path,
    compose: ComposeResult,
    output_path: Path,
    *,
    on_progress: ProgressCallback | None = None,
) -> str:
    """Run prediction; on auto, fall back from Gemini quota errors to OpenAI."""
    if provider == "openai":
        _openai_predict(prompt, style_reference_path, compose, output_path, on_progress=on_progress)
        return "openai"

    if provider == "auto" and not _gemini_api_key() and _openai_api_key():
        _openai_predict(prompt, style_reference_path, compose, output_path, on_progress=on_progress)
        return "openai"

    try:
        _gemini_predict(prompt, style_reference_path, compose, output_path, on_progress=on_progress)
        return "gemini"
    except ImageGenerationError as exc:
        if provider == "auto" and is_quota_error(exc) and _openai_api_key():
            emit_progress(
                on_progress,
                step="predict",
                substep="fallback",
                message="Gemini quota unavailable — falling back to OpenAI…",
                progress=48,
            )
            _openai_predict(prompt, style_reference_path, compose, output_path, on_progress=on_progress)
            return "openai (gemini quota fallback)"
        raise


def predict_visual_flyer(
    gig_id: str,
    *,
    study_id: str = HATCH_CONSTRAINTS.study_id,
    round_num: int = 1,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
    predict_fn: Callable[..., str] | None = None,
) -> dict[str, Any]:
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

    provider_pref = _resolve_predict_provider()
    provider_used = provider_pref

    if dry_run:
        out_path.write_bytes(b"")
        card_path.write_bytes(b"")
    else:
        if band_photo is None or not band_photo.is_file():
            raise RuntimeError("Band photo required for visual prediction")
        if not _predict_api_available(provider_pref) and provider_pref != "auto":
            raise RuntimeError(f"No API key available for VISUAL_PREDICT_PROVIDER={provider_pref}")
        if not _gemini_api_key() and not _openai_api_key():
            raise RuntimeError(
                "No image API key found. Set GOOGLE_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY."
            )

        size = parse_output_size(os.getenv("OPENAI_IMAGE_SIZE", "1024x1536"))
        with tempfile.TemporaryDirectory(prefix="gigflyers-predict-") as tmp:
            compose = _prepare_hatch_canvas(band_photo, size, Path(tmp))
            emit_progress(
                on_progress,
                step="predict",
                message="Calling AI to predict flyer from style reference…",
                progress=40,
            )
            if predict_fn is not None:
                provider_used = predict_fn(prompt, style_ref, compose, out_path, on_progress=on_progress)
            else:
                provider_used = _run_predict(
                    provider_pref,
                    prompt,
                    style_ref,
                    compose,
                    out_path,
                    on_progress=on_progress,
                )

            enforce_photo_bbox(out_path, compose, force=True)
            validation = validate_flyer_photo(out_path, band_photo, compose)
            if not validation.passed:
                failed = [c for c in validation.checks if not c.get("passed")]
                detail = "; ".join(f"{c.get('name')}: {c.get('detail')}" for c in failed[:3])
                raise RuntimeError(f"Photo validation failed after prediction — {detail}")

    method_label = f"AI image prediction ({provider_used})"
    extra_lines = [
        "AI path: review visually against reference panel",
        f"Study: {study.title}",
        f"Provider: {provider_used}",
    ]
    build_evaluation_card(
        reference_path=style_ref,
        generated_path=out_path if out_path.stat().st_size > 0 else style_ref,
        output_path=card_path,
        study_title=study.title,
        method=method_label,
        constraint_report=None,
        extra_checklist_lines=extra_lines,
    )

    manifest = {
        "gig_id": gig_id,
        "round": round_num,
        "study_id": study_id,
        "method": "ai_visual_predict",
        "provider": provider_used,
        "provider_preference": provider_pref,
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
