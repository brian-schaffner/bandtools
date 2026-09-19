"""Three-panel evaluation card: reference | generated | checklist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from visual_constraints import ConstraintReport

PANEL_W = 1024
PANEL_H = 1536
CARD_W = PANEL_W * 3
CARD_H = PANEL_H + 80  # title strip
TITLE_H = 80
BG = (28, 28, 32)
TEXT = (240, 240, 240)
PASS = (76, 175, 80)
FAIL = (229, 57, 53)
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
    target_w, target_h = size
    ratio = min(target_w / img.width, target_h / img.height)
    new_w = max(1, int(img.width * ratio))
    new_h = max(1, int(img.height * ratio))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (245, 235, 220))
    ox = (target_w - new_w) // 2
    oy = (target_h - new_h) // 2
    canvas.paste(resized, (ox, oy))
    return canvas


def _draw_checklist_panel(
    size: tuple[int, int],
    *,
    study_title: str,
    method: str,
    report: ConstraintReport | None,
    extra_lines: list[str] | None = None,
) -> Image.Image:
    w, h = size
    panel = Image.new("RGB", size, (248, 246, 240))
    draw = ImageDraw.Draw(panel)
    title_font = _load_font(28)
    body_font = _load_font(22)
    small_font = _load_font(18)

    y = 24
    draw.text((24, y), "CONSTRAINT CHECKLIST", fill=(20, 20, 20), font=title_font)
    y += 44
    draw.text((24, y), study_title[:60], fill=(80, 80, 80), font=small_font)
    y += 28
    draw.text((24, y), f"Method: {method}", fill=(80, 80, 80), font=small_font)
    y += 40

    if report is None:
        draw.text((24, y), "No automated constraint report.", fill=(80, 80, 80), font=body_font)
    else:
        status = "PASS" if report.passed else "FAIL"
        color = PASS if report.passed else FAIL
        draw.text((24, y), f"Overall: {status}", fill=color, font=title_font)
        y += 48
        for check in report.checks:
            mark = "✓" if check.passed else "✗"
            color = PASS if check.passed else FAIL
            draw.text((24, y), mark, fill=color, font=body_font)
            line = f"{check.label}"
            draw.text((52, y), line[:42], fill=(30, 30, 30), font=body_font)
            y += 26
            draw.text((52, y), check.detail[:55], fill=(100, 100, 100), font=small_font)
            y += 32
            if y > h - 120:
                draw.text((24, y), "…", fill=MUTED, font=body_font)
                break

    if extra_lines:
        y = max(y + 20, h - 24 - len(extra_lines) * 26)
        for line in extra_lines[-4:]:
            draw.text((24, y), line[:58], fill=(100, 100, 100), font=small_font)
            y += 26

    return panel


def build_evaluation_card(
    *,
    reference_path: Path,
    generated_path: Path,
    output_path: Path,
    study_title: str,
    method: str,
    constraint_report: ConstraintReport | None = None,
    panel_labels: tuple[str, str, str] = ("Reference poster", "Generated flyer", "Checklist"),
    extra_checklist_lines: list[str] | None = None,
) -> dict[str, Any]:
    """Compose 3-panel evaluation card PNG."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    card = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(card)
    label_font = _load_font(24)

    ref_panel = _fit_image(reference_path, (PANEL_W, PANEL_H))
    gen_panel = _fit_image(generated_path, (PANEL_W, PANEL_H)) if generated_path.is_file() else Image.new(
        "RGB", (PANEL_W, PANEL_H), (60, 60, 60)
    )
    checklist = _draw_checklist_panel(
        (PANEL_W, PANEL_H),
        study_title=study_title,
        method=method,
        report=constraint_report,
        extra_lines=extra_checklist_lines,
    )

    for idx, (panel, label) in enumerate(
        zip((ref_panel, gen_panel, checklist), panel_labels, strict=True)
    ):
        x = idx * PANEL_W
        card.paste(panel, (x, TITLE_H))
        tw = draw.textlength(label, font=label_font)
        draw.text((x + (PANEL_W - tw) / 2, 28), label, fill=TEXT, font=label_font)

    card.save(output_path, format="PNG")
    return {
        "path": str(output_path),
        "width": CARD_W,
        "height": CARD_H,
        "constraint_pass": constraint_report.passed if constraint_report else None,
    }
