"""Three-panel eval card for two-pass shell pipeline: reference | shell | personalized."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PANEL_W = 1024
PANEL_H = 1536
CARD_W = PANEL_W * 3
CARD_H = PANEL_H + 80
TITLE_H = 80
BG = (28, 28, 32)
TEXT = (240, 240, 240)
MUTED = (160, 160, 168)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fit_image(path: Path, size: tuple[int, int]) -> Image.Image:
    img = Image.open(path).convert("RGB")
    tw, th = size
    ratio = min(tw / img.width, th / img.height)
    nw, nh = max(1, int(img.width * ratio)), max(1, int(img.height * ratio))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (245, 235, 220))
    ox, oy = (tw - nw) // 2, (th - nh) // 2
    canvas.paste(resized, (ox, oy))
    return canvas


def _brief_panel(
    size: tuple[int, int],
    *,
    shell_title: str,
    shell_id: str,
    venue: str,
    date: str,
    extra: list[str] | None = None,
) -> Image.Image:
    w, h = size
    panel = Image.new("RGB", size, (248, 246, 240))
    draw = ImageDraw.Draw(panel)
    title_font = _load_font(28)
    body_font = _load_font(22)
    small_font = _load_font(18)
    y = 24
    draw.text((24, y), "TWO-PASS CHECKLIST", fill=(20, 20, 20), font=title_font)
    y += 44
    draw.text((24, y), shell_title[:55], fill=(80, 80, 80), font=small_font)
    y += 28
    draw.text((24, y), f"Shell: {shell_id}", fill=(80, 80, 80), font=small_font)
    y += 28
    draw.text((24, y), "Pass 1: design shell (placeholders)", fill=(80, 80, 80), font=small_font)
    y += 24
    draw.text((24, y), "Pass 2: personalize + locked photo/logo", fill=(80, 80, 80), font=small_font)
    y += 40
    draw.text((24, y), f"Venue: {venue}", fill=(20, 20, 20), font=body_font)
    y += 32
    draw.text((24, y), f"Date: {date}", fill=(20, 20, 20), font=body_font)
    y += 48
    for line in extra or []:
        draw.text((24, y), line[:70], fill=(60, 60, 60), font=small_font)
        y += 24
    return panel


def build_shell_evaluation_card(
    *,
    reference_path: Path,
    shell_path: Path,
    personalized_path: Path,
    output_path: Path,
    shell_title: str,
    shell_id: str,
    venue: str,
    date: str,
    extra_lines: list[str] | None = None,
) -> Path:
    card = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(card)
    title_font = _load_font(24)
    labels = ("Style reference", "Pass 1 design shell", "Pass 2 personalized")
    paths = (reference_path, shell_path, personalized_path)
    for i, (label, path) in enumerate(zip(labels, paths)):
        x0 = i * PANEL_W
        draw.rectangle([x0, 0, x0 + PANEL_W, TITLE_H], fill=(18, 18, 22))
        draw.text((x0 + 24, 26), label, fill=TEXT, font=title_font)
        panel = _fit_image(path, (PANEL_W, PANEL_H))
        card.paste(panel, (x0, TITLE_H))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    card.save(output_path, format="PNG")
    return output_path
