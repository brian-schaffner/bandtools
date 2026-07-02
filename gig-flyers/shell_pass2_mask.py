"""Edit mask for shell pass 2 — protect design, open only text bands."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from shell_references import ShellReference
from shell_asset_integrate import ShellPass2Compose
from shell_asset_policy import AssetMode
from shell_render_registry import get_render_spec
from shell_render_spec import frac_boxes_to_pixels
from shell_text_slots import typography_text_zones

_PROTECT = (255, 255, 255, 255)
_EDIT = (0, 0, 0, 0)


def text_edit_zones(
    size: tuple[int, int],
    photo_clear_bbox: tuple[int, int, int, int],
    shell: ShellReference | None = None,
    *,
    asset_mode: AssetMode | None = None,
) -> list[tuple[int, int, int, int]]:
    """Transparent mask regions where OpenAI may replace placeholder text."""
    del photo_clear_bbox, asset_mode
    if shell is not None:
        return typography_text_zones(size, shell)

    w, h = size
    margin_x = int(w * 0.03)
    return [
        (margin_x, int(h * 0.05), w - margin_x, int(h * 0.20)),
        (margin_x, int(h * 0.78), w - margin_x, int(h * 0.98)),
    ]


def preserve_zones(
    size: tuple[int, int],
    shell: ShellReference | None,
    *,
    photo_clear_bbox: tuple[int, int, int, int] = (0, 0, 0, 0),
    logo_bbox: tuple[int, int, int, int] = (0, 0, 0, 0),
    asset_mode: AssetMode | None = None,
    protect_pad: int = 20,
) -> list[tuple[int, int, int, int]]:
    """Regions that must never be edited by OpenAI."""
    w, h = size
    zones: list[tuple[int, int, int, int]] = []

    if shell is not None:
        spec = get_render_spec(shell)
        zones.extend(frac_boxes_to_pixels(size, spec.preserve_regions))

    if asset_mode != "typography_only" and photo_clear_bbox[2] > photo_clear_bbox[0]:
        pl = max(0, photo_clear_bbox[0] - protect_pad)
        pt = max(0, photo_clear_bbox[1] - protect_pad)
        pr = min(w, photo_clear_bbox[2] + protect_pad)
        pb = min(h, photo_clear_bbox[3] + protect_pad)
        zones.append((pl, pt, pr, pb))

    if asset_mode != "typography_only" and logo_bbox[2] > logo_bbox[0]:
        ll = max(0, logo_bbox[0] - protect_pad)
        lt = max(0, logo_bbox[1] - protect_pad)
        lr = min(w, logo_bbox[2] + protect_pad)
        lb = min(h, logo_bbox[3] + protect_pad)
        zones.append((ll, lt, lr, lb))

    return zones


def build_personalize_mask(
    size: tuple[int, int],
    *,
    photo_clear_bbox: tuple[int, int, int, int],
    logo_bbox: tuple[int, int, int, int],
    shell: ShellReference | None = None,
    asset_mode: AssetMode | None = None,
    protect_pad: int = 20,
) -> Image.Image:
    """Mostly protect pass-1 art; only registry text bands are editable."""
    w, h = size
    mask = Image.new("RGBA", (w, h), _PROTECT)
    draw = ImageDraw.Draw(mask)
    for zone in text_edit_zones(size, photo_clear_bbox, shell, asset_mode=asset_mode):
        draw.rectangle(zone, fill=_EDIT)

    for zone in preserve_zones(
        size,
        shell,
        photo_clear_bbox=photo_clear_bbox,
        logo_bbox=logo_bbox,
        asset_mode=asset_mode,
        protect_pad=protect_pad,
    ):
        draw.rectangle(zone, fill=_PROTECT)

    return mask


def build_slot_mask(
    size: tuple[int, int],
    zone: tuple[int, int, int, int],
    *,
    pad: int = 4,
) -> Image.Image:
    """Protect entire canvas except one tight placeholder slot."""
    w, h = size
    mask = Image.new("RGBA", (w, h), _PROTECT)
    x1, y1, x2, y2 = zone
    draw = ImageDraw.Draw(mask)
    draw.rectangle(
        [max(0, x1 - pad), max(0, y1 - pad), min(w, x2 + pad), min(h, y2 + pad)],
        fill=_EDIT,
    )
    return mask


def enforce_shell_design(output_path: Path, compose: ShellPass2Compose, *, asset_pad: int = 20) -> bool:
    """Paste pass-1 shell pixels back everywhere except text bands and asset slots."""
    if not output_path.is_file():
        return False

    model = Image.open(output_path).convert("RGBA")
    shell = compose.shell_layer.convert("RGBA")
    orig_w, orig_h = compose.canvas_size
    if model.size != (orig_w, orig_h):
        model = model.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
    if shell.size != (orig_w, orig_h):
        shell = shell.resize((orig_w, orig_h), Image.Resampling.LANCZOS)

    keep_model = Image.new("L", (orig_w, orig_h), 255)
    draw = ImageDraw.Draw(keep_model)
    draw.rectangle([0, 0, orig_w, orig_h], fill=255)
    for zone in compose.text_edit_zones:
        draw.rectangle(zone, fill=0)
    if compose.asset_mode != "typography_only":
        for bbox in (compose.photo_clear_bbox, compose.logo_bbox):
            if bbox[2] <= bbox[0]:
                continue
            draw.rectangle(
                [
                    max(0, bbox[0] - asset_pad),
                    max(0, bbox[1] - asset_pad),
                    min(orig_w, bbox[2] + asset_pad),
                    min(orig_h, bbox[3] + asset_pad),
                ],
                fill=255,
            )

    # mask 255 → shell (pass-1 art), mask 0 → model (personalized text)
    result = Image.composite(shell, model, keep_model)
    result.convert("RGB").save(output_path, format="PNG")
    return True
