"""Edit mask for shell pass 2 — protect design, open only text bands."""

from __future__ import annotations

from PIL import Image, ImageDraw

from shell_references import ShellReference

_PROTECT = (255, 255, 255, 255)
_EDIT = (0, 0, 0, 0)

_MID_TITLE_FAMILIES = frozenset(
    {
        "blues_screenprint",
        "punk_screenprint",
        "modern_club",
        "gritty_sidebar_bill",
        "blues_festival",
        "reggae_flyer",
    }
)


def text_edit_zones(
    size: tuple[int, int],
    photo_clear_bbox: tuple[int, int, int, int],
    shell: ShellReference | None = None,
) -> list[tuple[int, int, int, int]]:
    """Transparent mask regions where OpenAI may replace placeholder text."""
    w, h = size
    _, photo_top, _, photo_bottom = photo_clear_bbox
    zones: list[tuple[int, int, int, int]] = []
    margin_x = int(w * 0.03)

    header_bottom = min(int(h * 0.24), max(int(h * 0.10), photo_top - 10))
    if header_bottom > int(h * 0.05):
        zones.append((margin_x, int(h * 0.02), w - margin_x, header_bottom))

    footer_top = max(int(h * 0.76), photo_bottom + 10)
    if footer_top < int(h * 0.96):
        zones.append((margin_x, footer_top, w - margin_x, int(h * 0.98)))

    between_top = photo_bottom + 8
    between_bottom = footer_top - 8
    if between_bottom - between_top >= int(h * 0.04):
        zones.append((margin_x, between_top, w - margin_x, between_bottom))

    if shell is not None and shell.design_family in _MID_TITLE_FAMILIES:
        mid_top = header_bottom + 6
        mid_bottom = photo_top - 6
        if mid_bottom - mid_top >= int(h * 0.05):
            zones.append((margin_x, mid_top, w - margin_x, mid_bottom))

    return zones


def build_personalize_mask(
    size: tuple[int, int],
    *,
    photo_clear_bbox: tuple[int, int, int, int],
    logo_bbox: tuple[int, int, int, int],
    shell: ShellReference | None = None,
    protect_pad: int = 20,
) -> Image.Image:
    """Mostly protect pass-1 art; only header/footer text bands are editable."""
    w, h = size
    mask = Image.new("RGBA", (w, h), _PROTECT)
    draw = ImageDraw.Draw(mask)
    for zone in text_edit_zones(size, photo_clear_bbox, shell):
        draw.rectangle(zone, fill=_EDIT)

    pl = max(0, photo_clear_bbox[0] - protect_pad)
    pt = max(0, photo_clear_bbox[1] - protect_pad)
    pr = min(w, photo_clear_bbox[2] + protect_pad)
    pb = min(h, photo_clear_bbox[3] + protect_pad)
    draw.rectangle([pl, pt, pr, pb], fill=_PROTECT)

    ll = max(0, logo_bbox[0] - protect_pad)
    lt = max(0, logo_bbox[1] - protect_pad)
    lr = min(w, logo_bbox[2] + protect_pad)
    lb = min(h, logo_bbox[3] + protect_pad)
    draw.rectangle([ll, lt, lr, lb], fill=_PROTECT)

    return mask
