#!/usr/bin/env python3
"""AI vision reviewer for generated flyer options.

Enforces the photo treatment doctrine: band photos are SOURCE ARTWORK, not inspiration.
The AI should never regenerate, redraw, or reinterpret the musicians.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any, Optional

from gig_calendar import GigEvent
from image_providers.photo_treatment import PHOTO_FORBIDDEN
from text_validation import (
    footer_prompt_lines,
    resolve_venue_address,
    validate_required_footer_text,
)
from progress_helper import ProgressCallback, emit_progress, heartbeat_during

ROOT = Path(__file__).resolve().parent

DEFAULT_VERDICT: dict[str, Any] = {
    "pass": True,
    "score": 8,
    "issues": [],
    "remake_recommended": False,
    "feedback_for_regen": "",
    "retry_count": 0,
    "display_note": "Passed",
    "members_visible": None,
    "text_errors": [],
    "confidence": None,
    "member_count_confidence": None,
}

_MEMBER_COUNT_CONFIDENCE_THRESHOLD = 0.8
_SERIOUS_REMAKE_KEYWORDS = (
    "unreadable",
    "misspell",
    "wrong venue",
    "wrong date",
    "wrong band",
    "incorrect venue",
    "incorrect date",
    "incorrect band",
    "distort",
    "warp",
    "mung",
    "face swap",
    "not legible",
    "cannot read",
    "illegible",
    "cropped off",
    "cut off",
    "cropping",
    "missing member",
    "cropped",
    "missing address",
    "missing venue",
    "no footer",
    "address missing",
    "grey bar",
    "gray bar",
    "placeholder bar",
)

_PHOTO_DISTORTION_KEYWORDS = (
    "distort",
    "warp",
    "mung",
    "face swap",
    "face change",
    "ai face",
    "stretched",
    "elongated",
    "squashed",
    "melt",
    "redraw",
    "regenerat",
    "restyl",
    "different people",
    "wrong person",
    "member cut off",
    "member cropped",
    "face cropped",
    "cropped awkwardly",
    "cropped off",
    "cut off",
    "cropping",
    "cropped",
    "missing member",
    "does not match",
    "do not match",
    "not match",
    "altered",
    "smoothened",
    "smoothed",
    "ai-styl",
)

_GRAPHICS_OVER_FACE_KEYWORDS = (
    "over face",
    "over faces",
    "on face",
    "on faces",
    "across face",
    "across faces",
    "covers face",
    "covering face",
    "cover face",
    "obscures face",
    "obscures faces",
    "obscuring face",
    "blocks face",
    "hiding face",
    "hidden by",
    "head covered",
    "face covered",
    "graphic over",
    "graphics over",
    "text over",
    "typography over",
    "starburst",
    "burst over",
)

_DOUBLE_PHOTO_KEYWORDS = (
    "double photo",
    "duplicate photo",
    "two photo",
    "two band photo",
    "second photo",
    "inset photo",
    "inset band",
    "overlapping photo",
    "photo on photo",
    "layered photo",
    "pasted on top",
    "photo pasted",
)

# Forbidden photo operations from the photo treatment doctrine
# These trigger automatic failure if detected in the generated flyer
_FORBIDDEN_OPERATION_KEYWORDS = (
    "repaint",
    "redraw",
    "inpaint",
    "outpaint",
    "replace face",
    "replaced face",
    "change expression",
    "changed expression",
    "invent limb",
    "invented limb",
    "extra arm",
    "extra leg",
    "extra finger",
    "change clothing",
    "changed clothing",
    "different outfit",
    "change instrument",
    "changed instrument",
    "different instrument",
    "hallucinate finger",
    "hallucinated finger",
    "wrong number of finger",
    "hallucinate guitar",
    "hallucinated guitar",
    "hallucinate people",
    "hallucinated people",
    "generate new human",
    "generated new human",
    "ai face enhancement",
    "beauty filter",
    "beautified",
    "style transfer",
    "stylized face",
    "artistic reinterpretation",
    "reimagined",
    "reinterpreted",
)


def _parse_confidence(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, conf))


def _is_trivial_text_error(error: str) -> bool:
    """Filter casing/punctuation nitpicks that should not trigger remake."""
    text = error.strip().lower()
    if not text:
        return True
    serious_markers = (
        "wrong venue",
        "wrong date",
        "wrong band",
        "incorrect venue",
        "incorrect date",
        "incorrect band",
        "misspell",
        "unreadable",
        "not legible",
        "illegible",
        "cannot read",
        "mcoo",
        "mccoon",
    )
    if any(marker in text for marker in serious_markers):
        return False
    trivial_markers = (
        "pm capital",
        "capitalized",
        "uppercase",
        "lowercase",
        "am/pm",
        " pm ",
        " am ",
        "pm vs",
        "vs pm",
        "time format",
        "time should read",
        "formatting",
        "hyphen",
        "en-dash",
        "en dash",
        "em-dash",
        "punctuation",
        "spacing",
        "apostrophe",
        "comma",
        "period",
        "casing",
        "capitalization",
        "showtime:",
    )
    if any(marker in text for marker in trivial_markers):
        return True
    if re.search(r"\b(pm|am)\b", text) and re.search(
        r"(capital|case|upper|lower|format)", text
    ):
        return True
    if re.search(r"7:00\s*pm", text) and "wrong" not in text and "misspell" not in text:
        return True
    return False


def _filter_text_errors(errors: list[str]) -> list[str]:
    return [e for e in errors if not _is_trivial_text_error(e)]


def _is_serious_issue(issue: str) -> bool:
    text = issue.lower()
    return any(keyword in text for keyword in _SERIOUS_REMAKE_KEYWORDS)


def _is_photo_distortion_issue(issue: str) -> bool:
    text = issue.lower()
    return any(keyword in text for keyword in _PHOTO_DISTORTION_KEYWORDS)


def _is_graphics_over_face_issue(issue: str) -> bool:
    text = issue.lower()
    if any(keyword in text for keyword in _GRAPHICS_OVER_FACE_KEYWORDS):
        return True
    if "face" not in text:
        return False
    return any(
        marker in text
        for marker in (
            "cover",
            "obscur",
            "block",
            "hidden",
            "over ",
            "across",
            "starburst",
            "graphic",
            "typography",
            "text ",
        )
    )


def _is_double_photo_issue(issue: str) -> bool:
    text = issue.lower()
    return any(keyword in text for keyword in _DOUBLE_PHOTO_KEYWORDS)


def _is_forbidden_operation_issue(issue: str) -> bool:
    """Check if an issue describes a forbidden photo operation from the treatment doctrine."""
    text = issue.lower()
    if any(keyword in text for keyword in _FORBIDDEN_OPERATION_KEYWORDS):
        return True
    for forbidden in PHOTO_FORBIDDEN:
        if forbidden.lower() in text:
            return True
    return False


def _is_photo_fidelity_issue(issue: str) -> bool:
    return (
        _is_photo_distortion_issue(issue)
        or _is_graphics_over_face_issue(issue)
        or _is_double_photo_issue(issue)
        or _is_forbidden_operation_issue(issue)
    )


def _is_member_count_issue(issue: str) -> bool:
    text = issue.lower()
    if "member" not in text:
        return False
    count_markers = (
        "visible",
        "of 4",
        "of 3",
        "of 5",
        "count",
        "only 3",
        "only 2",
        "only 1",
        "four members",
        "three members",
    )
    return any(marker in text for marker in count_markers)


def _member_count_fail(
    members_visible: Optional[int],
    expected_members: Optional[int],
    member_confidence: Optional[float],
    *,
    has_reference: bool = False,
) -> bool:
    if has_reference:
        return False
    if expected_members is None or members_visible is None:
        return False
    if members_visible >= expected_members:
        return False
    if members_visible > expected_members - 1:
        return False
    if member_confidence is None:
        return False
    return member_confidence >= _MEMBER_COUNT_CONFIDENCE_THRESHOLD


def max_reviewer_retries() -> int:
    """Max auto-remakes per option after initial generation (default 1)."""
    try:
        return max(0, int(os.getenv("AI_REVIEWER_MAX_REMAKES", "1")))
    except ValueError:
        return 1


def reviewer_enabled() -> bool:
    return os.getenv("AI_REVIEWER_ENABLED", "1").strip().lower() not in {"0", "false", "no"}


def _display_note(verdict: dict[str, Any]) -> str:
    issues = [str(i).strip() for i in verdict.get("issues", []) if str(i).strip()]
    retries = int(verdict.get("retry_count") or 0)
    passed = bool(verdict.get("pass"))

    if retries > 0 and not passed:
        reason = issues[0] if issues else "quality fixes applied"
        return f"Remade ({retries}x): {reason}"
    if passed:
        return "Passed"
    if issues:
        return f"Review note: {issues[0]}"
    return "Needs review"


def _expected_member_count(selected_photo: Optional[dict[str, Any]]) -> Optional[int]:
    if not selected_photo:
        return None
    count = selected_photo.get("member_count")
    if count is not None:
        try:
            return int(count)
        except (TypeError, ValueError):
            return None
    photo_type = str(selected_photo.get("type", ""))
    if photo_type in {"group_standing", "group_energetic", "group"}:
        return 4
    return None


def build_review_prompt(
    event: GigEvent,
    variation: dict[str, Any],
    *,
    band_name: Optional[str] = None,
    selected_photo: Optional[dict[str, Any]] = None,
    has_reference: bool = False,
) -> str:
    band = band_name or os.getenv("GIG_CALENDAR_BAND", "Lindsey Lane Band")
    layout_label = variation.get("label") or variation.get("id", "flyer")
    member_count = _expected_member_count(selected_photo)
    address = resolve_venue_address(event)
    footer_block = "\n".join(footer_prompt_lines(event, band=band))
    member_line = ""
    if has_reference:
        member_line = (
            "- PRIMARY photo check: compare the band photo region in IMAGE 2 to IMAGE 1.\n"
            "- PASS if faces, instruments, poses, and composition match IMAGE 1.\n"
            "- Do NOT fail based on counting members — overlap, angle, and lighting make counts unreliable.\n"
            "- FAIL photo fidelity ONLY for clear distortion vs IMAGE 1: warped faces, wrong people, "
            "obvious crop removing a person, or AI-restyled band photo.\n"
            "- Color tinting or print treatment on the photo is OK if composition and people match IMAGE 1."
        )
    elif member_count:
        member_line = (
            f"- Reference photo has {member_count} band members.\n"
            f"- FAIL member count ONLY when clearly fewer than {member_count} are visible "
            f"(obvious crop cutting someone off, not uncertainty).\n"
            "- Set member_count_confidence 0.0-1.0; only recommend remake for member loss when "
            "confidence >= 0.8 that someone is clearly missing."
        )
    else:
        member_line = (
            "- All band members from the reference photo should remain visible.\n"
            "- FAIL only on obvious crop removing a person, not ambiguous angles."
        )
    
    forbidden_ops = ", ".join(PHOTO_FORBIDDEN[:8])
    photo_doctrine_block = (
        "\nPHOTO TREATMENT DOCTRINE (automatic failure if violated):\n"
        "The band photo is SOURCE ARTWORK — never regenerated, redrawn, or reinterpreted.\n"
        f"FORBIDDEN operations: {forbidden_ops}...\n"
        "ALLOWED: crop, scale, rotate <=2°, brightness, contrast, film grain, vignette, color toning.\n"
        "FAIL if any forbidden operation was applied to the musicians in the photo.\n"
    )

    reference_block = ""
    if has_reference:
        reference_block = (
            "\nYou will see TWO images:\n"
            "IMAGE 1 = ORIGINAL REFERENCE BAND PHOTO (ground truth — sacred, do not alter people)\n"
            "IMAGE 2 = GENERATED FLYER (evaluate the band photo region in this image)\n\n"
            "PRIMARY CHECK — BAND PHOTO FIDELITY (compare IMAGE 2 band photo region to IMAGE 1):\n"
            "- The band photo must match IMAGE 1 at 100% fidelity — same faces, instruments, poses, composition\n"
            "- FAIL for ANY warping, stretching, re-posing, AI face changes, smoothing, or munging vs IMAGE 1\n"
            "- FAIL if a band member is clearly cropped out or replaced vs IMAGE 1 (not uncertain counting)\n"
            "- FAIL if flyer graphics or typography (starburst, date badge, text blocks) overlap or cover band faces\n"
            "- FAIL if the band photo appears twice (duplicate/inset photo over the main band photo)\n"
            f"{member_line}\n"
            "- Layout creativity is OK around the photo — the photo itself must match IMAGE 1\n\n"
        )

    return (
        "You are a QA reviewer for regional band flyers. "
        "Fail only serious problems. Do not nitpick authentic photocopy imperfections.\n\n"
        f"{photo_doctrine_block}\n"
        f"{reference_block}"
        "PRIMARY CHECK — TEXT ACCURACY (on IMAGE 2 / generated flyer):\n"
        f"- Venue must be correct and readable: {event.venue}\n"
        f"- Band must be correct and readable: {band}\n"
        f"- Date must match the gig: {event.event_date.strftime('%A, %B %d, %Y')}\n"
        f"- Time must be present and readable (content matters, not casing): {event.time_label or 'TBA'}\n"
        f"{f'- Address must be present and readable: {address}' + chr(10) if address else ''}"
        f"{footer_block}\n"
        "TEXT RULES — IGNORE (never fail or remake for these alone):\n"
        "- am/pm/PM/AM casing (7:00pm vs 7:00 PM vs 7:00 pm is NOT a failure)\n"
        "- Minor punctuation, hyphens vs en-dashes, SHOWTIME: prefix, comma placement\n"
        "- Typography style unless text is unreadable\n\n"
        "TEXT RULES — FAIL only for:\n"
        "- Wrong venue name, wrong date, wrong band name\n"
        "- Actual misspellings (not capitalization)\n"
        "- Unreadable or missing critical text\n"
        "- Missing venue address or venue name in footer\n"
        "- Grey/blank decorative bar instead of footer text\n\n"
        f"Layout: {layout_label}\n"
        f"Gig: {event.title}\n\n"
        "REMAKE BAR: recommend remake for photo fidelity failures (distorted/changed faces vs reference), "
        "graphics or text overlapping band faces, duplicate/overlapping band photos, "
        "wrong gig info, unreadable text, or obvious missing band member when NO reference image is provided. "
        "When reference is provided, compare IMAGE 2 photo region to IMAGE 1 — set photo_matches_reference=false "
        "and remake_recommended=true for ANY photo fidelity failure (distortion, duplicate photo, graphics on faces). "
        "Do NOT remake for member-count uncertainty alone. Do NOT remake for PM casing or minor punctuation.\n\n"
        "Return JSON only with keys:\n"
        '- pass (bool): true if acceptable to show the user\n'
        "- score (int 1-10)\n"
        "- confidence (float 0-1): overall confidence in your verdict\n"
        "- issues (array of short strings): serious issues only\n"
        "- remake_recommended (bool): true ONLY for serious issues listed above\n"
        "- feedback_for_regen (string): specific fix instructions for the image model\n"
        "- photo_matches_reference (bool or null): when reference provided, true if band photo region matches IMAGE 1\n"
        "- members_visible (int or null): optional telemetry — do NOT use alone to fail when reference is provided\n"
        "- member_count_confidence (float 0-1 or null): optional telemetry for member count guess\n"
        '- text_errors (array of strings): substantive spelling/content errors only (not casing)\n'
    )


def _mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "image/png"


def _encode_image_part(path: Path) -> dict[str, Any]:
    b64 = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{_mime_type(path)};base64,{b64}"},
    }


def build_review_message_content(
    prompt: str,
    flyer_path: Path,
    reference_photo_path: Optional[Path] = None,
) -> list[Any]:
    content: list[Any] = [{"type": "text", "text": prompt}]
    if reference_photo_path and reference_photo_path.is_file():
        content.append({"type": "text", "text": "IMAGE 1 — REFERENCE BAND PHOTO:"})
        content.append(_encode_image_part(reference_photo_path))
        content.append({"type": "text", "text": "IMAGE 2 — GENERATED FLYER:"})
    content.append(_encode_image_part(flyer_path))
    return content


def _normalize_verdict(
    raw: dict[str, Any],
    retry_count: int = 0,
    expected_members: Optional[int] = None,
    has_reference: bool = False,
) -> dict[str, Any]:
    raw_text_errors = [str(t).strip() for t in raw.get("text_errors", []) if str(t).strip()]
    text_errors = _filter_text_errors(raw_text_errors)
    issues = [str(i).strip() for i in raw.get("issues", []) if str(i).strip()]
    issues = _filter_text_errors(issues)
    issues = text_errors + [i for i in issues if i not in text_errors]

    if has_reference:
        issues = [i for i in issues if not _is_member_count_issue(i)]

    members_visible = raw.get("members_visible")
    try:
        members_visible = int(members_visible) if members_visible is not None else None
    except (TypeError, ValueError):
        members_visible = None

    confidence = _parse_confidence(raw.get("confidence"))
    member_confidence = _parse_confidence(raw.get("member_count_confidence"))
    photo_matches_reference = raw.get("photo_matches_reference")
    if isinstance(photo_matches_reference, str):
        photo_matches_reference = photo_matches_reference.strip().lower() in {"true", "1", "yes"}

    if _member_count_fail(
        members_visible,
        expected_members,
        member_confidence,
        has_reference=has_reference,
    ):
        issue = f"Only {members_visible} of {expected_members} band members clearly visible"
        if issue not in issues:
            issues.insert(0, issue)
    elif not has_reference:
        issues = [
            i
            for i in issues
            if not (
                _is_member_count_issue(i)
                and members_visible is not None
                and expected_members is not None
                and members_visible >= expected_members - 1
            )
        ]

    score = raw.get("score", 8)
    try:
        score = max(1, min(10, int(score)))
    except (TypeError, ValueError):
        score = 8

    photo_issues = [i for i in issues if _is_photo_fidelity_issue(i)]
    serious_issues = [i for i in issues if _is_serious_issue(i)]
    has_serious_text = bool(text_errors)
    model_remake = bool(raw.get("remake_recommended", False))
    reference_photo_fail = has_reference and photo_matches_reference is False

    if has_reference and photo_matches_reference is True:
        layout_issues = [
            i
            for i in issues
            if _is_graphics_over_face_issue(i) or _is_double_photo_issue(i)
        ]
        if layout_issues:
            photo_issues = layout_issues
            model_remake = True
        else:
            photo_issues = []
            serious_issues = [i for i in serious_issues if not _is_photo_fidelity_issue(i)]
            issues = [
                i
                for i in issues
                if not _is_photo_fidelity_issue(i) and not _is_member_count_issue(i)
            ]
            model_remake = model_remake and (has_serious_text or bool(serious_issues))
    elif reference_photo_fail:
        model_remake = True
        if not photo_issues:
            issue = "Band photo region does not match reference"
            if issue not in issues:
                issues.insert(0, issue)
            photo_issues = [issue]
    elif has_reference and photo_issues:
        model_remake = True

    remake = False
    if has_serious_text:
        remake = True
        score = min(score, 6)
    elif reference_photo_fail or photo_issues:
        remake = True
        score = min(score, 5)
    elif photo_issues and model_remake:
        remake = True
    elif not has_reference and serious_issues and score <= 5:
        remake = True
    elif _member_count_fail(
        members_visible,
        expected_members,
        member_confidence,
        has_reference=has_reference,
    ):
        remake = True
        score = min(score, 5)

    passed = bool(raw.get("pass", score >= 7))
    if remake or reference_photo_fail or (has_reference and photo_issues):
        passed = False
    elif not serious_issues and not has_serious_text and not photo_issues:
        passed = True
        if score < 7 and not model_remake:
            score = max(score, 7)

    if reference_photo_fail:
        passed = False
        remake = True
        score = min(score, 5)

    feedback = str(raw.get("feedback_for_regen", "") or "").strip()
    if remake and not feedback and issues:
        if any(_is_photo_fidelity_issue(i) or _is_member_count_issue(i) for i in issues):
            feedback = (
                "Preserve the exact reference band photo — "
                "same faces, instruments, poses, all members visible, no distortion, no crop, no face changes."
            )
        else:
            feedback = "; ".join(issues[:3])

    verdict = {
        "pass": passed,
        "score": score,
        "issues": issues,
        "remake_recommended": remake,
        "feedback_for_regen": feedback,
        "retry_count": retry_count,
        "members_visible": members_visible,
        "text_errors": text_errors,
        "confidence": confidence,
        "member_count_confidence": member_confidence,
        "photo_matches_reference": photo_matches_reference,
    }
    if raw.get("photo_validation") is not None:
        verdict["photo_validation"] = raw["photo_validation"]
    verdict["display_note"] = _display_note(verdict)
    return verdict


def review_flyer_image(
    image_path: Path,
    style: dict[str, Any],
    event: GigEvent,
    variation: dict[str, Any],
    *,
    dry_run: bool = False,
    retry_count: int = 0,
    option: str = "",
    on_progress: Optional[ProgressCallback] = None,
    reference_photo_path: Optional[Path] = None,
    selected_photo: Optional[dict[str, Any]] = None,
    tier: str = "",
) -> dict[str, Any]:
    """Review a generated flyer image. Returns pass/fail verdict with remake guidance."""
    opt = option or "?"
    expected_members = _expected_member_count(selected_photo)
    has_reference = bool(reference_photo_path and reference_photo_path.is_file())

    emit_progress(
        on_progress,
        step="review",
        substep="start",
        message=f"Reviewing option {opt} (text + photo fidelity)…",
        option=opt,
        attempt=retry_count + 1 if retry_count else 0,
        option_phase="reviewing",
        option_progress=100,
    )

    if dry_run or not reviewer_enabled():
        return dict(DEFAULT_VERDICT)

    if not os.getenv("OPENAI_API_KEY"):
        return dict(DEFAULT_VERDICT)

    if not image_path.is_file() or image_path.stat().st_size < 512:
        return _normalize_verdict(
            {
                "pass": False,
                "score": 3,
                "issues": ["Image file missing or too small"],
                "remake_recommended": True,
                "feedback_for_regen": "Regenerate a complete readable flyer image.",
            },
            retry_count=retry_count,
            expected_members=expected_members,
            has_reference=has_reference,
        )

    photo_validation: Optional[dict[str, Any]] = None
    resolved_tier = tier or str(variation.get("tier") or variation.get("id") or "medium")
    wild_mode = resolved_tier == "wild" or variation.get("generation_mode") == "full_canvas_wild"
    if has_reference and reference_photo_path is not None and not wild_mode:
        try:
            import tempfile

            from image_providers.reference_compose import (
                parse_output_size,
                prepare_photo_compose,
                validate_flyer_photo,
            )

            resolved_tier = tier or str(variation.get("tier") or variation.get("id") or "medium")
            output_size = parse_output_size(os.getenv("OPENAI_IMAGE_SIZE", "1024x1536"))
            with tempfile.TemporaryDirectory(prefix="gigflyers-review-") as tmp:
                compose = prepare_photo_compose(
                    reference_photo_path,
                    output_size,
                    tier=resolved_tier,
                    work_dir=Path(tmp),
                    create_mask=False,
                )
                validation = validate_flyer_photo(image_path, reference_photo_path, compose)
                photo_validation = validation.to_dict()
                if not validation.passed:
                    failed = [c for c in validation.checks if not c.get("passed")]
                    issue_lines = [f"{c['name']}: {c['detail']}" for c in failed]
                    return _normalize_verdict(
                        {
                            "pass": False,
                            "score": 3,
                            "issues": issue_lines,
                            "remake_recommended": True,
                            "feedback_for_regen": (
                                "Band photo fidelity failed automated checks — "
                                "do not modify or redraw the band photo; typography and graphics only "
                                "in areas around the existing photo."
                            ),
                            "photo_matches_reference": False,
                            "photo_validation": photo_validation,
                        },
                        retry_count=retry_count,
                        expected_members=expected_members,
                        has_reference=has_reference,
                    )
        except Exception as exc:
            return _normalize_verdict(
                {
                    "pass": False,
                    "score": 2,
                    "issues": [f"photo_validation_error: {exc.__class__.__name__}: {exc}"],
                    "remake_recommended": True,
                    "feedback_for_regen": "Regenerate flyer — automated photo validation could not run.",
                    "photo_matches_reference": False,
                },
                retry_count=retry_count,
                expected_members=expected_members,
                has_reference=has_reference,
            )

    try:
        from openai import OpenAI
    except ImportError:
        return dict(DEFAULT_VERDICT)

    model = os.getenv("AI_REVIEWER_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    prompt = build_review_prompt(
        event,
        variation,
        selected_photo=selected_photo,
        has_reference=has_reference,
    )
    content = build_review_message_content(prompt, image_path, reference_photo_path)

    try:
        with heartbeat_during(
            on_progress,
            step="review",
            message_template="AI reviewer still checking option {option}… ({seconds}s)",
            option=opt,
            attempt=retry_count + 1 if retry_count else 0,
        ):
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                response_format={"type": "json_object"},
                max_tokens=600,
            )
        raw = json.loads(response.choices[0].message.content or "{}")
        verdict = _normalize_verdict(
            raw,
            retry_count=retry_count,
            expected_members=expected_members,
            has_reference=has_reference,
        )

        if has_reference and reference_photo_path is not None and not wild_mode:
            try:
                import tempfile

                from image_providers.reference_compose import (
                    parse_output_size,
                    prepare_photo_compose,
                    validate_flyer_photo,
                )

                resolved_tier = tier or str(variation.get("tier") or variation.get("id") or "medium")
                output_size = parse_output_size(os.getenv("OPENAI_IMAGE_SIZE", "1024x1536"))
                with tempfile.TemporaryDirectory(prefix="gigflyers-review-post-") as tmp:
                    compose = prepare_photo_compose(
                        reference_photo_path,
                        output_size,
                        tier=resolved_tier,
                        work_dir=Path(tmp),
                        create_mask=False,
                    )
                    post_validation = validate_flyer_photo(
                        image_path, reference_photo_path, compose
                    )
                    if photo_validation is None:
                        photo_validation = post_validation.to_dict()
                    if not post_validation.passed:
                        failed = [c for c in post_validation.checks if not c.get("passed")]
                        issue_lines = [f"{c['name']}: {c['detail']}" for c in failed]
                        issues = list(verdict.get("issues", []))
                        for line in issue_lines:
                            if line not in issues:
                                issues.insert(0, line)
                        verdict = _normalize_verdict(
                            {
                                **verdict,
                                "pass": False,
                                "issues": issues,
                                "remake_recommended": True,
                                "photo_matches_reference": False,
                                "photo_validation": photo_validation,
                                "score": min(int(verdict.get("score", 8)), 4),
                            },
                            retry_count=retry_count,
                            expected_members=expected_members,
                            has_reference=has_reference,
                        )
            except Exception:
                pass

        if photo_validation is not None:
            verdict = {**verdict, "photo_validation": photo_validation}

        issues = verdict.get("issues", [])
        issue_text = issues[0] if issues else "no major issues"
        emit_progress(
            on_progress,
            step="review",
            substep="verdict",
            message=f"Score {verdict['score']}/10 — {issue_text}",
            detail="; ".join(issues) if issues else "Passed",
            option=opt,
            attempt=retry_count + 1 if retry_count else 0,
        )
        if verdict.get("remake_recommended"):
            emit_progress(
                on_progress,
                step="review",
                substep="remake",
                message=f"Remake recommended for option {opt}",
                detail=verdict.get("feedback_for_regen", ""),
                option=opt,
                attempt=retry_count + 1,
            )
        elif verdict.get("pass"):
            passed_msg = "Remake passed" if retry_count else "Passed"
            emit_progress(
                on_progress,
                step="review",
                substep="passed",
                message=f"Option {opt}: {passed_msg}",
                option=opt,
            )
        return verdict
    except Exception as exc:  # noqa: BLE001
        fallback = dict(DEFAULT_VERDICT)
        fallback["display_note"] = f"Review skipped: {exc.__class__.__name__}"
        emit_progress(
            on_progress,
            step="review",
            substep="error",
            message=f"Option {opt}: review error — {exc.__class__.__name__}",
            option=opt,
        )
        return fallback
