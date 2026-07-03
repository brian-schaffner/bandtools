"""Pass 1: generate a design shell from a reference poster (placeholders only)."""

from __future__ import annotations

import base64
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from output_paths import get_output_dir, output_relative
from shell_model_policy import ShellModelChoice, select_model_for_step
from shell_openai_edit import shell_images_edit
from shell_references import PLACEHOLDER_LABELS, ShellReference, get_shell

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
OUT_DIR = get_output_dir() / "shell_design"


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
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def build_shell_briefing_sheet(
    shell: ShellReference,
    out_path: Path,
    size: tuple[int, int] = (1024, 1536),
) -> Path:
    """Style reference + empty render zone for pass-1 shell generation."""
    w, h = size
    sheet = Image.new("RGB", size, (242, 235, 220))
    draw = ImageDraw.Draw(sheet)
    label = _load_font(18)

    ref_path = shell.image_path()
    if ref_path.is_file():
        ref = Image.open(ref_path).convert("RGB")
        ref_h = int(h * 0.42)
        ref_fit = _fit(ref, w - 48, ref_h - 36)
        sheet.paste(ref_fit, ((w - ref_fit.width) // 2, 24))
    draw.text((24, 4), f"SHELL REFERENCE — {shell.design_family}", fill=(80, 20, 20), font=label)

    render_y = int(h * 0.46)
    draw.rectangle([24, render_y, w - 24, h - 24], outline=(179, 27, 27), width=3)
    placeholders = " · ".join(PLACEHOLDER_LABELS)
    draw.text(
        (36, render_y + 12),
        f"RENDER DESIGN SHELL HERE\n(use placeholder text only: {placeholders})\n"
        "No real band names. No photos. Focus on best visual design.",
        fill=(100, 100, 100),
        font=label,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG")
    return out_path


def build_shell_prompt(shell: ShellReference) -> str:
    labels = ", ".join(PLACEHOLDER_LABELS)
    return (
        "You are an expert gig poster designer creating a MASTER DESIGN SHELL.\n\n"
        "The briefing sheet shows a STYLE REFERENCE at top. Match its visual language, "
        "layout hierarchy, palette, and graphic complexity — but create an ORIGINAL design.\n\n"
        "CRITICAL RULES FOR PASS 1:\n"
        f"  • Use ONLY placeholder text: {labels}\n"
        "  • Do NOT use any real band, venue, or festival names\n"
        "  • Do NOT include band photos, logos, faces, people, or silhouettes\n"
        "  • Portrait/photo zones must be EMPTY — flat color blocks, texture, or "
        "decorative frame only (no placeholder people)\n"
        "  • Focus purely on the strongest visual design\n"
        "  • Render ONE finished vertical poster (2:3) in the outlined zone, "
        "then expand to fill the entire canvas\n"
        "  • Remove briefing labels and boxes\n\n"
        f"Style family: {shell.design_family}\n"
        f"Design guidance: {shell.shell_prompt}\n\n"
        "Layout rules:\n"
        + "\n".join(f"  • {rule}" for rule in shell.layout_rules)
        + "\n\nOutput a single complete design shell image."
    )


def generate_design_shell_openai(
    shell: ShellReference,
    output_path: Path,
    *,
    briefing_path: Path | None = None,
    model_choice: ShellModelChoice | None = None,
    on_openai_call: Callable[[], None] | None = None,
) -> Path:
    from openai import OpenAI

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY required")

    choice = model_choice or select_model_for_step(shell, "pass1")
    client = OpenAI(api_key=api_key)

    with tempfile.TemporaryDirectory(prefix="shell-pass1-") as tmp:
        tmp_path = Path(tmp)
        briefing = briefing_path or tmp_path / "shell_briefing.png"
        if not briefing.is_file():
            build_shell_briefing_sheet(shell, briefing)
        prompt = build_shell_prompt(shell)
        with briefing.open("rb") as f:
            response = shell_images_edit(
                client,
                image=f,
                prompt=prompt,
                choice=choice,
                on_call=on_openai_call,
            )
        item = response.data[0]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if item.b64_json:
            output_path.write_bytes(base64.b64decode(item.b64_json))
        elif item.url:
            with urllib.request.urlopen(item.url, timeout=120) as resp:
                output_path.write_bytes(resp.read())
        else:
            raise RuntimeError("OpenAI returned no image data")
    return output_path


def generate_design_shell(
    shell_id: str,
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    shell = get_shell(shell_id)
    if shell is None:
        raise ValueError(f"Unknown shell: {shell_id}")

    output_dir = output_dir or OUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = shell.id
    briefing_path = output_dir / f"{stem}_pass1_briefing.png"
    shell_path = output_dir / f"{stem}_design_shell.png"

    build_shell_briefing_sheet(shell, briefing_path)
    generate_design_shell_openai(shell, shell_path, briefing_path=briefing_path)

    manifest = {
        "shell_id": shell.id,
        "shell_title": shell.title,
        "design_family": shell.design_family,
        "briefing_rel": output_relative(briefing_path),
        "shell_rel": output_relative(shell_path),
        "prompt": build_shell_prompt(shell),
    }
    manifest_path = output_dir / f"{stem}_pass1_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
