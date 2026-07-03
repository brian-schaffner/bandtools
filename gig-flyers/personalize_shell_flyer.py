"""Pass 2: personalize a design shell with band photo, logo, and gig facts."""

from __future__ import annotations

import base64
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable, Literal

from dotenv import load_dotenv
from PIL import Image, ImageFont

from gig_calendar import GigEvent
from output_paths import get_output_dir, output_relative
from shell_asset_integrate import (
    CANVAS_BACKGROUND,
    ShellPass2Compose,
    _clear_pad_for_slot,
    _sample_backdrop_ring,
    _sample_zone_mean,
    clear_photo_slot,
    compose_integrated_assets,
    enforce_shell_photo,
    enforce_shell_logo,
    fit_layer_in_box,
    integrate_band_logo,
    integration_summary,
    photo_slot_for_shell,
    photo_slot_label,
    placement_zones,
)
from shell_asset_policy import AssetMode, asset_mode_for_shell, asset_mode_label, uses_band_logo, uses_band_photo

FinalRoute = Literal["text_only", "photo_logo"]
from shell_pass2_mask import build_personalize_mask, build_slot_mask, enforce_shell_design, text_edit_zones
from shell_model_policy import ShellModelChoice, ShellStep, model_choice_for_step, select_model_for_step
from shell_openai_edit import shell_images_edit
from shell_references import PLACEHOLDER_LABELS, ShellReference, get_shell
from shell_deterministic_text import apply_deterministic_text
from shell_render_registry import get_render_spec
from shell_text_slots import placeholder_values, slot_prompt, typography_text_zones
from structured_layout.band_mark import find_band_logo
from text_validation import footer_prompt_lines, typography_hierarchy_prompt_lines

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
DEFAULT_PHOTO = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"
OUT_DIR = get_output_dir() / "shell_design"


def _event_facts_block(*, venue: str, date: str, time: str, band: str, address: str = "") -> str:
    lines = [
        "EVENT FACTS (copy exactly — replace all placeholders):",
        f"  Band / headliner: {band}",
        f"  Venue: {venue}",
        f"  Date: {date}",
        f"  Time: {time}",
    ]
    if address:
        lines.append(f"  Address: {address}")
    return "\n".join(lines)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fit(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    ratio = min(max_w / img.width, max_h / img.height)
    nw, nh = max(1, int(img.width * ratio)), max(1, int(img.height * ratio))
    out = img.resize((nw, nh), Image.Resampling.LANCZOS)
    if img.mode == "RGBA":
        return out
    return out.convert("RGB")


def _resolve_logo(band: str, paper: tuple[int, int, int]) -> Path:
    logo = find_band_logo(band, paper=paper)
    if logo is not None and logo.is_file():
        return logo
    name = "lindsey-lane-band-light.png" if sum(paper) / 3 < 128 else "lindsey-lane-band-dark.png"
    return ROOT / "assets/logos" / name


def _exact_text_block(
    *,
    venue: str,
    date: str,
    time: str,
    band: str,
    address: str = "",
) -> str:
    lines = [
        "EXACT TEXT (copy character-for-character; match shell typography but never misspell):",
        f'  Band name: "{band}"',
        f'  Venue: "{venue}"',
        f'  Date: "{date}"',
        f'  Time: "{time}"',
    ]
    if address:
        lines.append(f'  Address: "{address}"')
    lines.extend(
        [
            "  • Do NOT re-type the band name from the logo artwork — use the quoted band name above",
            '  • Do NOT change "Lane" to "Land" or alter capitalization',
            "  • Replace HEADLINER / VENUE NAME / DATE / TIME placeholders with these exact strings",
        ]
    )
    return "\n".join(lines)


def build_personalize_prompt(
    shell: ShellReference,
    *,
    venue: str,
    date: str,
    time: str,
    band: str,
    address: str = "",
    event: GigEvent | None = None,
    asset_mode: AssetMode | None = None,
) -> str:
    slot = photo_slot_for_shell(shell)
    mode = asset_mode or asset_mode_for_shell(shell)
    spec = get_render_spec(shell) if shell is not None else None
    slot_desc = photo_slot_label(slot)
    mode_desc = asset_mode_label(mode)
    typo_lines: list[str] = []
    footer_lines: list[str] = []
    if event is not None:
        typo_lines = typography_hierarchy_prompt_lines(event, band=band)
        footer_lines = footer_prompt_lines(event, band=band)

    if mode == "typography_only":
        asset_block = (
            f"ASSET MODE: {mode_desc}\n"
            "  • Do NOT add any band photo, portrait, or pasted photo rectangle\n"
            f"  • Replace HEADLINER with the band name \"{band}\" rendered in the SAME "
            "hand-lettered / psychedelic / wood-type style as the shell — the band name IS the visual hero\n"
            "  • Do not add a separate logo badge — the typography carries the band identity\n\n"
        )
    elif spec is not None and spec.photo_style == "hero_illustration":
        asset_block = (
            f"RENDER SPEC: hero illustration (printed artwork, not a photo frame)\n"
            "  • Band artwork is pre-composited as high-contrast printed illustration — LOCKED\n"
            "  • Do NOT add borders, mats, drop shadows, or a second band image\n"
            "  • Change ONLY placeholder text in the editable bands\n\n"
        )
    else:
        asset_block = (
            f"ASSET MODE: {mode_desc}\n"
            "The canvas contains:\n"
            "  • PASS 1 DESIGN SHELL as the full background\n"
            f"  • ONE band photo already composited in the {slot_desc} — LOCKED\n"
            "  • BAND LOGO on a tinted badge — LOCKED\n\n"
            f"  • CRITICAL: There is exactly ONE band photo (in the {slot_desc}). "
            "Do NOT draw or duplicate band members anywhere else\n\n"
        )

    return (
        "You are personalizing an APPROVED DESIGN SHELL for a real gig.\n\n"
        "DESIGN PRESERVATION (critical):\n"
        "  • The pass-1 shell art is LOCKED — keep every color block, border, texture, "
        "grain, illustration, and printing effect exactly as on the input canvas\n"
        "  • Change ONLY placeholder text in the editable bands — do NOT simplify, "
        "flatten, recolor, or redesign the poster\n"
        "  • Do not replace panel layouts with plain parchment or single-color backgrounds\n\n"
        f"{asset_block}"
        "Your job:\n"
        "  • Swap placeholder text for the exact event facts below — match the shell's "
        "existing typography style\n"
        "  • Never overpaint hero illustration, decorative frames, or locked assets\n\n"
        + ("\n".join(typo_lines) + "\n" if typo_lines else "")
        + ("\n".join(footer_lines) + "\n" if footer_lines else "")
        + f"{_exact_text_block(venue=venue, date=date, time=time, band=band, address=address)}\n\n"
        f"{shell.personalize_prompt}\n\n"
        f"{_event_facts_block(venue=venue, date=date, time=time, band=band, address=address)}\n\n"
        "Output one complete personalized gig flyer."
    )


def build_personalize_canvas(
    shell_image_path: Path,
    photo_path: Path,
    logo_path: Path,
    out_dir: Path,
    *,
    shell: ShellReference | None = None,
    size: tuple[int, int] = (1024, 1536),
    asset_mode: AssetMode | None = None,
) -> tuple[Path, Path, tuple[int, int, int, int], tuple[int, int, int, int], ShellPass2Compose | None]:
    """Paste shell + styled photo/logo; return canvas, mask, bboxes, compose context."""
    w, h = size
    shell_img = Image.open(shell_image_path).convert("RGB")
    shell_fit = _fit(shell_img, w, h)
    canvas = Image.new("RGB", size, (242, 235, 220))
    ox = (w - shell_fit.width) // 2
    oy = (h - shell_fit.height) // 2
    canvas.paste(shell_fit, (ox, oy))
    shell_rgba = canvas.convert("RGBA")
    shell_layer = shell_rgba.copy()

    raw_photo = Image.open(photo_path)
    raw_logo = Image.open(logo_path)
    mode = asset_mode or (asset_mode_for_shell(shell) if shell is not None else "photo_inset")
    spec = get_render_spec(shell) if shell is not None else None
    empty_layer = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    photo_layer = empty_layer
    logo_layer = empty_layer
    px, py, lx, ly = 0, 0, 0, 0
    photo_zone = (0, 0, 0, 0)
    backdrop = CANVAS_BACKGROUND if shell is None else (242, 235, 220)
    clear_pad = 0

    if shell is not None and uses_band_photo(mode):
        zones = placement_zones(size, shell)
        photo_zone = zones["photo"]
        slot = photo_slot_for_shell(shell)
        backdrop = _sample_backdrop_ring(shell_rgba, photo_zone)
        clear_pad = _clear_pad_for_slot(slot)
        photo_layer, logo_layer, (px, py), (lx, ly) = compose_integrated_assets(
            shell_rgba, raw_photo, raw_logo, shell, size,
        )
    elif shell is not None and spec is not None and spec.uses_band_logo():
        zones = placement_zones(size, shell)
        logo_zone = zones["logo"]
        logo_backdrop = _sample_zone_mean(shell_rgba, logo_zone)
        logo_layer = integrate_band_logo(raw_logo, shell, zone_color=logo_backdrop)
        logo_layer = fit_layer_in_box(logo_layer, logo_zone)
        lx = logo_zone[2] - logo_layer.width
        ly = logo_zone[1] + (logo_zone[3] - logo_zone[1] - logo_layer.height) // 2
    elif shell is None:
        photo_layer = _fit(raw_photo.convert("RGBA"), int(w * 0.38), int(h * 0.20))
        px, py = 40, int(h * 0.62)
        logo_layer = _fit(raw_logo.convert("RGBA"), int(w * 0.42), int(h * 0.12))
        lx = w - logo_layer.width - 40
        ly = int(h * 0.78)
        photo_zone = (px, py, px + photo_layer.width, py + photo_layer.height)
        backdrop = (242, 235, 220)
        clear_pad = 24
        mode = "photo_inset"

    canvas_rgba = shell_rgba.copy()
    photo_clear_bbox = (0, 0, 0, 0)
    if shell is not None and uses_band_photo(mode):
        photo_clear_bbox = clear_photo_slot(
            canvas_rgba, photo_zone, backdrop=backdrop, pad=clear_pad,
        )
        canvas_rgba.alpha_composite(photo_layer, (px, py))
    elif shell is None:
        photo_clear_bbox = clear_photo_slot(
            canvas_rgba, photo_zone, backdrop=backdrop, pad=clear_pad,
        )
        canvas_rgba.alpha_composite(photo_layer, (px, py))
        canvas_rgba.alpha_composite(logo_layer, (lx, ly))
    if shell is not None and spec is not None and spec.uses_band_logo():
        canvas_rgba.alpha_composite(logo_layer, (lx, ly))
    canvas = canvas_rgba.convert("RGB")

    photo_bbox = (px, py, px + photo_layer.width, py + photo_layer.height)
    logo_bbox = (lx, ly, lx + logo_layer.width, ly + logo_layer.height)

    out_dir.mkdir(parents=True, exist_ok=True)
    canvas_path = out_dir / "pass2_canvas.png"
    canvas.save(canvas_path, format="PNG")

    mask = build_personalize_mask(
        size,
        photo_clear_bbox=photo_clear_bbox,
        logo_bbox=logo_bbox,
        shell=shell,
        asset_mode=mode if shell is not None else "photo_inset",
    )
    mask_path = out_dir / "pass2_mask.png"
    mask.save(mask_path, format="PNG")

    compose: ShellPass2Compose | None = None
    if shell is not None:
        edit_zones = tuple(text_edit_zones(size, photo_clear_bbox, shell, asset_mode=mode))
        compose = ShellPass2Compose(
            photo_bbox=photo_bbox,
            photo_clear_bbox=photo_clear_bbox,
            photo_layer=photo_layer.copy(),
            logo_bbox=logo_bbox,
            logo_layer=logo_layer.copy(),
            shell_layer=shell_layer.copy(),
            text_edit_zones=edit_zones,
            canvas_size=size,
            asset_mode=mode,
            backdrop_rgb=backdrop,
        )
    return canvas_path, mask_path, photo_bbox, logo_bbox, compose


def _parse_canvas_size(size: str) -> tuple[int, int]:
    raw = (size or "1024x1536").strip().lower()
    w, h = raw.split("x", 1)
    return int(w), int(h)


def _shell_canvas_rgba(shell_image_path: Path, size: tuple[int, int]) -> Image.Image:
    w, h = size
    shell_img = Image.open(shell_image_path).convert("RGB")
    shell_fit = _fit(shell_img, w, h)
    canvas = Image.new("RGB", size, (242, 235, 220))
    ox = (w - shell_fit.width) // 2
    oy = (h - shell_fit.height) // 2
    canvas.paste(shell_fit, (ox, oy))
    return canvas.convert("RGBA")


def _write_openai_image(item: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if item.b64_json:
        path.write_bytes(base64.b64decode(item.b64_json))
    elif item.url:
        with urllib.request.urlopen(item.url, timeout=120) as resp:
            path.write_bytes(resp.read())
    else:
        raise RuntimeError("OpenAI returned no image data")


def personalize_shell_typography_sequential(
    shell: ShellReference,
    shell_image_path: Path,
    output_path: Path,
    *,
    band: str,
    venue: str,
    date: str,
    time: str,
    client: Any,
    model_choice: ShellModelChoice,
    on_openai_call: Callable[[], None] | None = None,
) -> Path:
    """Replace each placeholder in a tight mask, restoring pass-1 art after every step."""
    spec = get_render_spec(shell)
    canvas_size = _parse_canvas_size(model_choice.size)
    shell_layer = _shell_canvas_rgba(shell_image_path, canvas_size)
    zones = typography_text_zones(canvas_size, shell)
    values = placeholder_values(band=band, venue=venue, date=date, time=time)
    empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    openai_labels = set(spec.openai_text_slots())

    with tempfile.TemporaryDirectory(prefix="shell-pass2-typo-") as tmp:
        work = Path(tmp) / "work.png"
        shell_layer.convert("RGB").save(work, format="PNG")

        if spec.text_engine in {"deterministic", "hybrid"}:
            det_labels = tuple(
                label for label in PLACEHOLDER_LABELS if label not in openai_labels
            )
            if det_labels:
                apply_deterministic_text(
                    work,
                    shell,
                    band=band,
                    venue=venue,
                    date=date,
                    time=time,
                    labels=det_labels,
                )

        edited_zones: list[tuple[int, int, int, int]] = []
        for label, zone in zip(PLACEHOLDER_LABELS, zones):
            if label not in openai_labels:
                continue
            value = values.get(label, "").strip()
            if not value:
                continue
            mask_path = Path(tmp) / f"mask_{label.replace(' ', '_')}.png"
            build_slot_mask(canvas_size, zone).save(mask_path, format="PNG")
            with work.open("rb") as image_f, mask_path.open("rb") as mask_f:
                response = shell_images_edit(
                    client,
                    image=image_f,
                    mask=mask_f,
                    prompt=slot_prompt(label, value, shell),
                    choice=model_choice,
                    on_call=on_openai_call,
                )
            _write_openai_image(response.data[0], work)
            edited_zones.append(zone)
            compose = ShellPass2Compose(
                photo_bbox=(0, 0, 0, 0),
                photo_clear_bbox=(0, 0, 0, 0),
                photo_layer=empty,
                logo_bbox=(0, 0, 0, 0),
                logo_layer=empty,
                shell_layer=shell_layer.copy(),
                text_edit_zones=tuple(edited_zones),
                canvas_size=canvas_size,
                asset_mode="typography_only",
            )
            enforce_shell_design(work, compose)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(work.read_bytes())
    return output_path


def personalize_shell_photo_registry(
    shell: ShellReference,
    shell_image_path: Path,
    photo_path: Path,
    logo_path: Path,
    output_path: Path,
    *,
    band: str,
    venue: str,
    date: str,
    time: str,
    client: Any,
    model_choice: ShellModelChoice,
    asset_mode: AssetMode | None = None,
    compose: ShellPass2Compose | None = None,
    initial_canvas_path: Path | None = None,
    on_openai_call: Callable[[], None] | None = None,
) -> Path:
    """Photo pass 2 driven by render spec — deterministic facts + tight OpenAI slots."""
    spec = get_render_spec(shell)
    compose_mode = asset_mode or asset_mode_for_shell(shell)
    canvas_size = _parse_canvas_size(model_choice.size)
    zones = typography_text_zones(canvas_size, shell)
    values = placeholder_values(band=band, venue=venue, date=date, time=time)
    openai_labels = set(spec.openai_text_slots())

    with tempfile.TemporaryDirectory(prefix="shell-pass2-photo-") as tmp:
        work = Path(tmp) / "work.png"
        if initial_canvas_path is not None and initial_canvas_path.is_file() and compose is not None:
            work.write_bytes(initial_canvas_path.read_bytes())
        else:
            canvas_path, _, _, _, built_compose = build_personalize_canvas(
                shell_image_path,
                photo_path,
                logo_path,
                Path(tmp),
                shell=shell,
                size=canvas_size,
                asset_mode=compose_mode,
            )
            work.write_bytes(canvas_path.read_bytes())
            compose = built_compose
        assert compose is not None

        if spec.text_engine in {"deterministic", "hybrid"}:
            det_labels = tuple(
                label for label in PLACEHOLDER_LABELS if label not in openai_labels
            )
            if det_labels:
                apply_deterministic_text(
                    work,
                    shell,
                    band=band,
                    venue=venue,
                    date=date,
                    time=time,
                    labels=det_labels,
                )

        edited_zones: list[tuple[int, int, int, int]] = []
        for label, zone in zip(PLACEHOLDER_LABELS, zones):
            if label not in openai_labels:
                continue
            value = values.get(label, "").strip()
            if not value:
                continue
            mask_path = Path(tmp) / f"mask_{label.replace(' ', '_')}.png"
            build_slot_mask(canvas_size, zone).save(mask_path, format="PNG")
            with work.open("rb") as image_f, mask_path.open("rb") as mask_f:
                response = shell_images_edit(
                    client,
                    image=image_f,
                    mask=mask_f,
                    prompt=slot_prompt(label, value, shell),
                    choice=model_choice,
                    on_call=on_openai_call,
                )
            _write_openai_image(response.data[0], work)
            edited_zones.append(zone)
            step_compose = ShellPass2Compose(
                photo_bbox=compose.photo_bbox,
                photo_clear_bbox=compose.photo_clear_bbox,
                photo_layer=compose.photo_layer.copy(),
                logo_bbox=compose.logo_bbox,
                logo_layer=compose.logo_layer.copy(),
                shell_layer=compose.shell_layer.copy(),
                text_edit_zones=tuple(edited_zones),
                canvas_size=canvas_size,
                asset_mode=compose_mode,
                backdrop_rgb=compose.backdrop_rgb,
            )
            enforce_shell_design(work, step_compose)
            enforce_shell_photo(work, step_compose)
            enforce_shell_logo(work, step_compose)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(work.read_bytes())
    return output_path


def personalize_shell_openai(
    shell: ShellReference,
    shell_image_path: Path,
    photo_path: Path,
    logo_path: Path,
    prompt: str,
    output_path: Path,
    *,
    band: str = "",
    venue: str = "",
    date: str = "",
    time: str = "",
    final_mode: FinalRoute | None = None,
    asset_mode: AssetMode | None = None,
    model_choice: ShellModelChoice | None = None,
    compose: ShellPass2Compose | None = None,
    initial_canvas_path: Path | None = None,
    on_openai_call: Callable[[], None] | None = None,
) -> Path:
    from openai import OpenAI

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    client = OpenAI(api_key=api_key)
    final_step: ShellStep = (
        "final_text"
        if final_mode == "text_only"
        else "final_photo"
        if final_mode == "photo_logo"
        else "final_text"
        if (asset_mode or asset_mode_for_shell(shell)) == "typography_only" and band
        else "final_photo"
    )
    choice = model_choice or select_model_for_step(shell, final_step, route=final_mode)

    use_typography = final_mode == "text_only" or (
        final_mode is None
        and (asset_mode or asset_mode_for_shell(shell)) == "typography_only"
        and band
    )
    if use_typography:
        text_choice = choice if choice.step == "final_text" else select_model_for_step(
            shell, "final_text", route=final_mode or "text_only",
        )
        return personalize_shell_typography_sequential(
            shell,
            shell_image_path,
            output_path,
            band=band,
            venue=venue,
            date=date,
            time=time,
            client=client,
            model_choice=text_choice,
            on_openai_call=on_openai_call,
        )

    compose_mode = asset_mode or asset_mode_for_shell(shell)
    spec = get_render_spec(shell)
    photo_choice = choice if choice.step == "final_photo" else select_model_for_step(
        shell, "final_photo", route=final_mode or "photo_logo",
    )

    if spec.text_engine in {"hybrid", "deterministic"}:
        return personalize_shell_photo_registry(
            shell,
            shell_image_path,
            photo_path,
            logo_path,
            output_path,
            band=band,
            venue=venue,
            date=date,
            time=time,
            client=client,
            model_choice=photo_choice,
            asset_mode=compose_mode,
            compose=compose,
            initial_canvas_path=initial_canvas_path,
            on_openai_call=on_openai_call,
        )

    with tempfile.TemporaryDirectory(prefix="shell-pass2-") as tmp:
        canvas_path, mask_path, _, _, compose = build_personalize_canvas(
            shell_image_path,
            photo_path,
            logo_path,
            Path(tmp),
            shell=shell,
            asset_mode=compose_mode,
        )
        with canvas_path.open("rb") as image_f, mask_path.open("rb") as mask_f:
            response = shell_images_edit(
                client,
                image=image_f,
                mask=mask_f,
                prompt=prompt,
                choice=photo_choice,
                on_call=on_openai_call,
            )
        item = response.data[0]
        _write_openai_image(item, output_path)
        if compose is not None:
            enforce_shell_design(output_path, compose)
            enforce_shell_photo(output_path, compose)
            enforce_shell_logo(output_path, compose)
    return output_path


def personalize_design_shell(
    event: GigEvent,
    shell_id: str,
    shell_image_path: Path,
    *,
    band: str = "Lindsey Lane Band",
    photo_path: Path | None = None,
    logo_path: Path | None = None,
    address: str = "",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    shell = get_shell(shell_id)
    if shell is None:
        raise ValueError(f"Unknown shell: {shell_id}")

    photo = photo_path or DEFAULT_PHOTO
    logo = logo_path or _resolve_logo(band, paper=(242, 235, 220))
    for label, path in [("shell", shell_image_path), ("photo", photo), ("logo", logo)]:
        if not path.is_file():
            raise FileNotFoundError(f"Missing {label}: {path}")

    output_dir = output_dir or OUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{event.gig_id}_{shell_id}"
    out_path = output_dir / f"{stem}_personalized.png"
    canvas_preview = output_dir / f"{stem}_pass2_canvas.png"

    date_str = event.event_date.strftime("%A, %B %d, %Y")
    time_str = event.time_label or "TBA"
    prompt = build_personalize_prompt(
        shell,
        venue=event.venue,
        date=date_str,
        time=time_str,
        band=band,
        address=address,
        event=event,
    )

    # Save pass-2 canvas preview for eval
    c_path, _, _, _, _ = build_personalize_canvas(
        shell_image_path, photo, logo, output_dir / f".{stem}_work", shell=shell,
    )
    canvas_preview.write_bytes(c_path.read_bytes())

    personalize_shell_openai(
        shell, shell_image_path, photo, logo, prompt, out_path,
        band=band, venue=event.venue, date=date_str, time=time_str,
    )

    manifest = {
        "gig_id": event.gig_id,
        "shell_id": shell.id,
        "shell_title": shell.title,
        "shell_image": str(shell_image_path),
        "photo": str(photo),
        "logo": str(logo),
        "personalized_rel": output_relative(out_path),
        "pass2_canvas_rel": output_relative(canvas_preview),
        "prompt": prompt,
        "asset_integration": integration_summary(shell),
    }
    manifest_path = output_dir / f"{stem}_pass2_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
