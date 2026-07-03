"""Google Gemini image provider."""

from __future__ import annotations

import mimetypes
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from image_providers.base import ImageProvider
from image_providers.errors import friendly_generation_error, is_retryable_429, retry_delay_seconds
from image_providers.reference_compose import (
    enforce_photo_bbox,
    parse_output_size,
    post_compose_enabled,
    prepare_canvas_with_photo,
    validate_flyer_photo,
)
from progress_helper import ProgressCallback, emit_progress, heartbeat_during

# Stable Nano Banana model; avoid preview alias that may hit zero free-tier quota.
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
MODEL_ALIASES = {
    "gemini-2.5-flash-preview-image": DEFAULT_GEMINI_IMAGE_MODEL,
    "gemini-2.0-flash-preview-image-generation": "gemini-2.0-flash-preview-image-generation",
}


def _gemini_api_key() -> str:
    key = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY is not set")
    return key


def _gemini_model() -> str:
    raw = os.getenv("GEMINI_IMAGE_MODEL", DEFAULT_GEMINI_IMAGE_MODEL).strip()
    return MODEL_ALIASES.get(raw, raw)


def _image_config(aspect_ratio: str) -> Any:
    from google.genai import types

    size = (os.getenv("GEMINI_IMAGE_SIZE") or "").strip()
    if size:
        return types.ImageConfig(aspect_ratio=aspect_ratio, image_size=size)
    return types.ImageConfig(aspect_ratio=aspect_ratio)


def _mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "image/jpeg"


def _extract_image_bytes(response: Any) -> bytes:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                if isinstance(data, bytes):
                    return data
                if isinstance(data, str):
                    import base64

                    return base64.b64decode(data)
    raise RuntimeError("Gemini response contained no image data")


class GeminiImageProvider(ImageProvider):
    name = "gemini"

    def generate(
        self,
        prompt: str,
        output_path: Path,
        *,
        reference_photo_path: Optional[Path] = None,
        on_progress: Optional[ProgressCallback] = None,
        option: str = "",
        attempt: int = 0,
        progress: int = 0,
        quality: Optional[str] = None,
        tier: str = "",
    ) -> None:
        model = _gemini_model()
        opt = option or "?"
        use_reference = reference_photo_path is not None and reference_photo_path.is_file()
        use_single_pass = use_reference and post_compose_enabled()
        mode = "photo-on-canvas" if use_single_pass else ("multimodal+reference" if use_reference else "text-to-image")
        emit_progress(
            on_progress,
            step="generate",
            substep="api_start",
            message=f"Calling Gemini {model} ({mode}) for option {opt}…",
            progress=progress,
            option=opt,
            attempt=attempt,
        )

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Install google-genai: pip install google-genai") from exc

        client = genai.Client(api_key=_gemini_api_key())
        aspect_ratio = os.getenv("GEMINI_IMAGE_ASPECT_RATIO", "2:3")

        contents: list[Any] = [prompt]
        compose = None
        image_bytes_for_api: Optional[bytes] = None

        if use_single_pass and reference_photo_path is not None:
            size = os.getenv("OPENAI_IMAGE_SIZE", "1024x1536")
            with tempfile.TemporaryDirectory(prefix="gigflyers-gemini-compose-") as tmp:
                compose = prepare_canvas_with_photo(
                    reference_photo_path,
                    parse_output_size(size),
                    tier=tier or "medium",
                    work_dir=Path(tmp),
                    create_mask=False,
                )
                image_bytes_for_api = compose.canvas_path.read_bytes()
                contents.append(
                    types.Part.from_bytes(
                        data=image_bytes_for_api,
                        mime_type="image/png",
                    )
                )
                contents.append(
                    "INPUT CANVAS: band photo is already on the flyer canvas. "
                    "Add typography and graphic design in the remaining cream paper areas only — "
                    "do not modify, redraw, duplicate, tile, or crop-repeat the band photo. "
                    "Do NOT add borders, frames, or mats around the band photo. "
                    "Copy event date, time, band name, and venue EXACTLY from the prompt."
                )
        elif use_reference:
            ref_bytes = reference_photo_path.read_bytes()
            contents.append(
                types.Part.from_bytes(data=ref_bytes, mime_type=_mime_type(reference_photo_path))
            )
            contents.append(
                "REFERENCE BAND PHOTO (previous image): paste onto flyer exactly — "
                "no distortion, no cropping band members, no face changes."
            )

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=_image_config(aspect_ratio),
        )

        def _call_api():
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

        def _call_with_optional_retry():
            try:
                return _call_api()
            except Exception as exc:
                if not is_retryable_429(exc):
                    raise
                delay = retry_delay_seconds(exc)
                emit_progress(
                    on_progress,
                    step="generate",
                    substep="retry",
                    message=f"Gemini rate limited, retrying in {int(delay)}s…",
                    detail=str(exc)[:200],
                    progress=progress,
                    option=opt,
                    attempt=attempt,
                )
                time.sleep(delay)
                return _call_api()

        try:
            with heartbeat_during(
                on_progress,
                step="generate",
                message_template="Gemini still generating option {option}… ({seconds}s)",
                progress=progress,
                option=opt,
                attempt=attempt,
            ):
                response = _call_with_optional_retry()
        except Exception as exc:
            raise friendly_generation_error(exc, "gemini") from exc

        image_bytes = _extract_image_bytes(response)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)

        if compose is not None and reference_photo_path is not None:
            enforce_photo_bbox(output_path, compose, force=True)

            validation = validate_flyer_photo(
                output_path, reference_photo_path, compose
            )
            if not validation.passed:
                failed = [c for c in validation.checks if not c.get("passed")]
                detail = "; ".join(
                    f"{c.get('name')}: {c.get('detail')}" for c in failed[:4]
                )
                raise RuntimeError(
                    f"Band photo validation failed after generation — {detail}"
                )

        size_mb = output_path.stat().st_size / (1024 * 1024)
        emit_progress(
            on_progress,
            step="generate",
            substep="saved",
            message=f"Saved option {opt} ({size_mb:.1f} MB)",
            progress=progress + 3,
            option=opt,
            attempt=attempt,
        )
