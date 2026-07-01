"""OpenAI gpt-image-1 provider (images.generate / images.edit)."""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Optional

from image_providers.base import ImageProvider
from image_providers.reference_compose import (
    ComposeResult,
    edit_mask_enabled,
    enforce_photo_bbox,
    parse_output_size,
    post_compose_enabled,
    prepare_canvas_with_photo,
    validate_flyer_photo,
)
from image_providers.typography_compose import (
    TYPOGRAPHY_ONLY_PROMPT_PREFIX,
    composite_typography_with_photo,
    prepare_blank_typography_canvas,
    typography_only_enabled,
)
from gen_timing import tier_for_option
from progress_helper import ProgressCallback, emit_progress, heartbeat_during

REFERENCE_EDIT_PROMPT_PREFIX = (
    "INPUT = FLYER CANVAS WITH BAND PHOTO ALREADY PLACED. "
    "The band photograph is pre-composited on the canvas — do NOT modify, redraw, regenerate, "
    "duplicate, tile, or add a second band image anywhere (including cropped footer strips). "
    "Do NOT draw people, faces, instruments, or band imagery in typography zones. "
    "Do NOT add borders, frames, mats, or decorative edges around the band photo. "
    "Do NOT add grey bars, brush strokes, or blank placeholder strips below the photo. "
    "Add flyer typography and graphic design ONLY in the cream paper areas around the existing photo. "
    "Venue name, date, band name, show time, and address must ALL appear and be clearly readable "
    "in the paper margins — never hidden under photo borders or frames. "
    "MANDATORY FOOTER: venue + full street address as readable text in the bottom margin. "
)


def _resolve_image_quality(quality: Optional[str] = None) -> str:
    return (quality or os.getenv("OPENAI_IMAGE_QUALITY", "medium")).strip().lower() or "medium"


def _resolve_input_fidelity() -> str:
    """OpenAI images.edit supports high (default) or low — always prefer high for band photos."""
    raw = os.getenv("OPENAI_IMAGE_INPUT_FIDELITY", "high").strip().lower()
    if raw in {"high", "max", "maximum"}:
        return "high"
    if raw == "low":
        return "low"
    return "high"


def _reference_required() -> bool:
    return os.getenv("OPENAI_IMAGE_USE_REFERENCE", "1").strip().lower() not in {"0", "false", "no"}


class OpenAIImageProvider(ImageProvider):
    name = "openai"

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
        use_reference = (
            reference_photo_path is not None
            and reference_photo_path.is_file()
            and _reference_required()
        )
        if (
            _reference_required()
            and reference_photo_path is not None
            and not reference_photo_path.is_file()
        ):
            raise RuntimeError(
                f"Band reference photo required but missing: {reference_photo_path}"
            )
        if _reference_required() and reference_photo_path is None:
            raise RuntimeError(
                "Band reference photo required (OPENAI_IMAGE_USE_REFERENCE=1) but none was provided"
            )

        use_single_pass = use_reference and post_compose_enabled() and not typography_only_enabled()
        use_typography_only = use_reference and typography_only_enabled()
        api_method = "images.edit" if use_reference else "images.generate"
        opt = option or "?"
        fidelity = _resolve_input_fidelity()
        if use_reference and fidelity != "high" and not use_typography_only:
            fidelity = "high"
        image_quality = _resolve_image_quality(quality)
        use_mask = use_single_pass and edit_mask_enabled()

        if use_typography_only:
            compose_mode = "typography-only"
        elif use_single_pass:
            compose_mode = "photo-on-canvas+mask"
        else:
            compose_mode = "direct"
        emit_progress(
            on_progress,
            step="generate",
            substep="api_start",
            message=(
                f"Calling OpenAI {api_method} for option {opt} "
                f"(fidelity={fidelity}, quality={image_quality}, compose={compose_mode})…"
            ),
            progress=progress,
            option=opt,
            attempt=attempt,
        )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install openai: pip install openai") from exc

        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
        size = os.getenv("OPENAI_IMAGE_SIZE", "1024x1536")
        output_size = parse_output_size(size)

        if use_typography_only:
            edit_prompt = f"{TYPOGRAPHY_ONLY_PROMPT_PREFIX}\n\n{prompt}"
        elif use_reference:
            edit_prompt = f"{REFERENCE_EDIT_PROMPT_PREFIX}\n\n{prompt}"
        else:
            edit_prompt = prompt

        compose: Optional[ComposeResult] = None
        edit_image_path = reference_photo_path
        mask_path: Optional[Path] = None

        resolved_tier = tier or tier_for_option(opt)

        if use_typography_only and reference_photo_path is not None:
            with tempfile.TemporaryDirectory(prefix="gigflyers-typo-") as tmp:
                work = Path(tmp)
                compose = prepare_blank_typography_canvas(
                    reference_photo_path,
                    output_size,
                    tier=resolved_tier,
                    work_dir=work,
                )
                typo_canvas = compose.canvas_path
                typography_tmp = work / "typography_raw.png"

                def _call_typography_api():
                    with typo_canvas.open("rb") as image_file:
                        return client.images.edit(
                            model=model,
                            image=image_file,
                            prompt=edit_prompt,
                            size=size,
                            quality=image_quality,
                            n=1,
                        )

                with heartbeat_during(
                    on_progress,
                    step="generate",
                    message_template="OpenAI still generating option {option}… ({seconds}s)",
                    progress=progress,
                    option=opt,
                    attempt=attempt,
                ):
                    response = _call_typography_api()

                item = response.data[0]
                output_path.parent.mkdir(parents=True, exist_ok=True)

                if item.b64_json:
                    typography_tmp.write_bytes(base64.b64decode(item.b64_json))
                elif item.url:
                    import urllib.request

                    with urllib.request.urlopen(item.url, timeout=120) as resp:
                        typography_tmp.write_bytes(resp.read())
                else:
                    raise RuntimeError("OpenAI image response had no b64_json or url")

                composite_typography_with_photo(typography_tmp, compose, output_path)

                validation = validate_flyer_photo(
                    output_path, reference_photo_path, compose
                )
                if not validation.passed:
                    failed = [c for c in validation.checks if not c.get("passed")]
                    detail = "; ".join(
                        f"{c.get('name')}: {c.get('detail')}" for c in failed[:4]
                    )
                    raise RuntimeError(
                        f"Band photo validation failed after typography compose — {detail}"
                    )
        elif use_single_pass and reference_photo_path is not None:
            with tempfile.TemporaryDirectory(prefix="gigflyers-compose-") as tmp:
                compose = prepare_canvas_with_photo(
                    reference_photo_path,
                    output_size,
                    tier=resolved_tier,
                    work_dir=Path(tmp),
                    create_mask=use_mask,
                )
                edit_image_path = compose.canvas_path
                mask_path = compose.mask_path if use_mask else None

                def _call_api():
                    with edit_image_path.open("rb") as image_file:
                        kwargs = {
                            "model": model,
                            "image": image_file,
                            "prompt": edit_prompt,
                            "size": size,
                            "quality": image_quality,
                            "input_fidelity": fidelity,
                            "n": 1,
                        }
                        if mask_path is not None and mask_path.is_file():
                            with mask_path.open("rb") as mask_file:
                                kwargs["mask"] = mask_file
                                return client.images.edit(**kwargs)
                        return client.images.edit(**kwargs)

                with heartbeat_during(
                    on_progress,
                    step="generate",
                    message_template="OpenAI still generating option {option}… ({seconds}s)",
                    progress=progress,
                    option=opt,
                    attempt=attempt,
                ):
                    response = _call_api()

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

                # gpt-image soft masks can redraw borders/photo — always restore PIL layer.
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
        else:
            def _call_api():
                if use_reference:
                    with edit_image_path.open("rb") as image_file:
                        return client.images.edit(
                            model=model,
                            image=image_file,
                            prompt=edit_prompt,
                            size=size,
                            quality=image_quality,
                            input_fidelity=fidelity,
                            n=1,
                        )
                return client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=image_quality,
                    n=1,
                )

            with heartbeat_during(
                on_progress,
                step="generate",
                substep="api_start",
                message_template="OpenAI still generating option {option}… ({seconds}s)",
                progress=progress,
                option=opt,
                attempt=attempt,
            ):
                response = _call_api()

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

        size_mb = output_path.stat().st_size / (1024 * 1024)
        emit_progress(
            on_progress,
            step="generate",
            substep="saved",
            message=f"Saved option {opt} ({size_mb:.1f} MB) via {api_method}",
            progress=progress + 3,
            option=opt,
            attempt=attempt,
        )
