"""Layout specification schema for Structured Layout Mode.

The AI Art Director produces a layout spec (JSON), NOT a finished image.
This spec is then rendered deterministically by the structured renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import json
import re

from text_validation import (
    SAFE_MARGIN_PX,
    is_house_series_gig,
    featured_act_line,
    resolve_venue_address,
    MONTH_NAME_RE,
    YEAR_RE,
    ADDRESS_ZIP_RE,
    ADDRESS_STREET_RE,
)
from structured_layout.layout_geometry import (
    MAX_TEXT_WIDTH_PCT,
    TEXT_MARGIN_X_PCT,
    VERTICAL_GAP_PCT,
    clamp_text_element,
    enforce_no_text_on_photo,
)


class TextAlignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class FontWeight(str, Enum):
    NORMAL = "normal"
    BOLD = "bold"
    BLACK = "black"


class PhotoPlacement(str, Enum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    FULL_BLEED = "full_bleed"


class DesignStyle(str, Enum):
    """Design styles for Structured Layout Mode options B and C."""
    HANDBILL = "handbill"  # Option B: Classic club handbill style
    COLLAGE = "collage"    # Option C: Paste-up collage style


@dataclass
class ColorSpec:
    """Color specification (RGB hex or named color)."""
    hex: str = "#000000"
    opacity: float = 1.0
    
    def to_dict(self) -> dict[str, Any]:
        return {"hex": self.hex, "opacity": self.opacity}
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColorSpec":
        return cls(hex=data.get("hex", "#000000"), opacity=data.get("opacity", 1.0))


@dataclass
class TextElement:
    """A text element in the layout."""
    content: str
    x: float  # Percentage of canvas width (0-100)
    y: float  # Percentage of canvas height (0-100)
    width: float  # Percentage of canvas width
    font_size: int  # Points
    font_family: str = "Helvetica Bold Condensed"
    font_weight: FontWeight = FontWeight.BOLD
    color: ColorSpec = field(default_factory=lambda: ColorSpec("#000000"))
    alignment: TextAlignment = TextAlignment.CENTER
    rotation: float = 0.0  # Degrees
    letter_spacing: float = 0.0  # Em units
    line_height: float = 1.2
    all_caps: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "font_size": self.font_size,
            "font_family": self.font_family,
            "font_weight": self.font_weight.value,
            "color": self.color.to_dict(),
            "alignment": self.alignment.value,
            "rotation": self.rotation,
            "letter_spacing": self.letter_spacing,
            "line_height": self.line_height,
            "all_caps": self.all_caps,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextElement":
        return cls(
            content=data["content"],
            x=data["x"],
            y=data["y"],
            width=data.get("width", 90),
            font_size=data.get("font_size", 48),
            font_family=data.get("font_family", "Helvetica Bold Condensed"),
            font_weight=FontWeight(data.get("font_weight", "bold")),
            color=ColorSpec.from_dict(data.get("color", {})),
            alignment=TextAlignment(data.get("alignment", "center")),
            rotation=data.get("rotation", 0.0),
            letter_spacing=data.get("letter_spacing", 0.0),
            line_height=data.get("line_height", 1.2),
            all_caps=data.get("all_caps", False),
        )


@dataclass
class PhotoFrame:
    """Photo placement and treatment specification.
    
    The photo is IMMUTABLE source artwork. Only these operations are allowed:
    - Crop, scale, rotate (<=2°), perspective correction
    - Masking, clipping, edge feathering
    - Color grading, halftone, film grain, paper texture
    """
    x: float  # Percentage of canvas width (0-100)
    y: float  # Percentage of canvas height (0-100)
    width: float  # Percentage of canvas width
    height: float  # Percentage of canvas height
    placement: PhotoPlacement = PhotoPlacement.CENTER
    rotation: float = 0.0  # Max ±2 degrees
    
    # Allowed photo treatments (PIL only, never AI)
    crop_top: float = 0.0  # Percentage to crop from top
    crop_bottom: float = 0.0
    crop_left: float = 0.0
    crop_right: float = 0.0
    
    # Edge treatments
    edge_feather: float = 0.0  # Pixels
    border_width: float = 0.0
    border_color: ColorSpec = field(default_factory=lambda: ColorSpec("#000000"))
    
    # Color grading (applied in PIL)
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    color_tint: Optional[ColorSpec] = None
    
    # Texture overlays
    film_grain: float = 0.0  # 0-1 strength
    halftone: bool = False
    halftone_dot_size: int = 4
    paper_texture: float = 0.0  # 0-1 strength
    
    # Masking
    mask_shape: str = "rectangle"  # rectangle, rounded, torn_edge, circle
    mask_corner_radius: float = 0.0
    
    # Blending
    blend_mode: str = "normal"  # normal, multiply, screen, overlay
    opacity: float = 1.0
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "placement": self.placement.value,
            "rotation": self.rotation,
            "crop": {
                "top": self.crop_top,
                "bottom": self.crop_bottom,
                "left": self.crop_left,
                "right": self.crop_right,
            },
            "edge_feather": self.edge_feather,
            "border_width": self.border_width,
            "border_color": self.border_color.to_dict(),
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "film_grain": self.film_grain,
            "halftone": self.halftone,
            "halftone_dot_size": self.halftone_dot_size,
            "paper_texture": self.paper_texture,
            "mask_shape": self.mask_shape,
            "mask_corner_radius": self.mask_corner_radius,
            "blend_mode": self.blend_mode,
            "opacity": self.opacity,
        }
        if self.color_tint:
            result["color_tint"] = self.color_tint.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhotoFrame":
        crop = data.get("crop", {})
        color_tint = None
        if data.get("color_tint"):
            color_tint = ColorSpec.from_dict(data["color_tint"])
        return cls(
            x=data["x"],
            y=data["y"],
            width=data["width"],
            height=data["height"],
            placement=PhotoPlacement(data.get("placement", "center")),
            rotation=max(-2.0, min(2.0, data.get("rotation", 0.0))),
            crop_top=crop.get("top", 0.0),
            crop_bottom=crop.get("bottom", 0.0),
            crop_left=crop.get("left", 0.0),
            crop_right=crop.get("right", 0.0),
            edge_feather=data.get("edge_feather", 0.0),
            border_width=data.get("border_width", 0.0),
            border_color=ColorSpec.from_dict(data.get("border_color", {})),
            brightness=data.get("brightness", 1.0),
            contrast=data.get("contrast", 1.0),
            saturation=data.get("saturation", 1.0),
            color_tint=color_tint,
            film_grain=data.get("film_grain", 0.0),
            halftone=data.get("halftone", False),
            halftone_dot_size=data.get("halftone_dot_size", 4),
            paper_texture=data.get("paper_texture", 0.0),
            mask_shape=data.get("mask_shape", "rectangle"),
            mask_corner_radius=data.get("mask_corner_radius", 0.0),
            blend_mode=data.get("blend_mode", "normal"),
            opacity=data.get("opacity", 1.0),
        )


@dataclass
class GraphicElement:
    """A decorative graphic element (box, line, shape, texture)."""
    element_type: str  # box, line, divider, starburst, stamp, tape, torn_edge
    x: float
    y: float
    width: float
    height: float
    fill_color: Optional[ColorSpec] = None
    stroke_color: Optional[ColorSpec] = None
    stroke_width: float = 0.0
    rotation: float = 0.0
    opacity: float = 1.0
    corner_radius: float = 0.0
    
    # Type-specific properties
    properties: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        result = {
            "element_type": self.element_type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "stroke_width": self.stroke_width,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "corner_radius": self.corner_radius,
            "properties": self.properties,
        }
        if self.fill_color:
            result["fill_color"] = self.fill_color.to_dict()
        if self.stroke_color:
            result["stroke_color"] = self.stroke_color.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphicElement":
        fill_color = None
        stroke_color = None
        if data.get("fill_color"):
            fill_color = ColorSpec.from_dict(data["fill_color"])
        if data.get("stroke_color"):
            stroke_color = ColorSpec.from_dict(data["stroke_color"])
        return cls(
            element_type=data["element_type"],
            x=data["x"],
            y=data["y"],
            width=data.get("width", 10),
            height=data.get("height", 10),
            fill_color=fill_color,
            stroke_color=stroke_color,
            stroke_width=data.get("stroke_width", 0.0),
            rotation=data.get("rotation", 0.0),
            opacity=data.get("opacity", 1.0),
            corner_radius=data.get("corner_radius", 0.0),
            properties=data.get("properties", {}),
        )


@dataclass
class BackgroundSpec:
    """Background specification."""
    color: ColorSpec = field(default_factory=lambda: ColorSpec("#F5F0E6"))  # Cream paper
    texture: str = "paper"  # paper, photocopy, cardboard, none
    texture_strength: float = 0.3
    grain_strength: float = 0.02
    margin_grain_only: bool = False  # restrict grain/xerox to margins outside photo
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "color": self.color.to_dict(),
            "texture": self.texture,
            "texture_strength": self.texture_strength,
            "grain_strength": self.grain_strength,
            "margin_grain_only": self.margin_grain_only,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackgroundSpec":
        return cls(
            color=ColorSpec.from_dict(data.get("color", {"hex": "#F5F0E6"})),
            texture=data.get("texture", "paper"),
            texture_strength=data.get("texture_strength", 0.3),
            grain_strength=data.get("grain_strength", 0.02),
            margin_grain_only=data.get("margin_grain_only", False),
        )


@dataclass
class LayoutSpec:
    """Complete layout specification for a flyer.
    
    This is the output of the AI Art Director. It defines every element
    of the flyer layout, which is then rendered deterministically.
    """
    # Canvas dimensions
    canvas_width: int = 1024
    canvas_height: int = 1536
    
    # Design metadata
    design_style: DesignStyle = DesignStyle.HANDBILL
    style_notes: str = ""
    
    # Background
    background: BackgroundSpec = field(default_factory=BackgroundSpec)
    
    # Photo placement (immutable source artwork)
    photo_frame: PhotoFrame = field(default_factory=lambda: PhotoFrame(
        x=5, y=35, width=90, height=50
    ))
    
    # Text elements (ordered by z-index, bottom to top)
    text_elements: list[TextElement] = field(default_factory=list)
    
    # Graphic elements (ordered by z-index, bottom to top)
    graphic_elements: list[GraphicElement] = field(default_factory=list)
    
    # Global effects
    photocopy_effect: float = 0.0  # 0-1 strength
    age_effect: float = 0.0  # 0-1 strength
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "design_style": self.design_style.value,
            "style_notes": self.style_notes,
            "background": self.background.to_dict(),
            "photo_frame": self.photo_frame.to_dict(),
            "text_elements": [t.to_dict() for t in self.text_elements],
            "graphic_elements": [g.to_dict() for g in self.graphic_elements],
            "photocopy_effect": self.photocopy_effect,
            "age_effect": self.age_effect,
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutSpec":
        return cls(
            canvas_width=data.get("canvas_width", 1024),
            canvas_height=data.get("canvas_height", 1536),
            design_style=DesignStyle(data.get("design_style", "handbill")),
            style_notes=data.get("style_notes", ""),
            background=BackgroundSpec.from_dict(data.get("background", {})),
            photo_frame=PhotoFrame.from_dict(data.get("photo_frame", {
                "x": 5, "y": 35, "width": 90, "height": 50
            })),
            text_elements=[TextElement.from_dict(t) for t in data.get("text_elements", [])],
            graphic_elements=[GraphicElement.from_dict(g) for g in data.get("graphic_elements", [])],
            photocopy_effect=data.get("photocopy_effect", 0.0),
            age_effect=data.get("age_effect", 0.0),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "LayoutSpec":
        return cls.from_dict(json.loads(json_str))


def _looks_like_venue_text(content: str, venue: str) -> bool:
    """True when content appears to be a venue headline (even if misspelled)."""
    content_norm = re.sub(r"\W+", " ", content.lower()).strip()
    venue_norm = re.sub(r"\W+", " ", venue.lower()).strip()
    if not content_norm or not venue_norm:
        return False
    if content_norm.startswith("featuring "):
        return False
    if MONTH_NAME_RE.search(content_norm) or YEAR_RE.search(content_norm):
        return False
    if ADDRESS_ZIP_RE.search(content_norm) or ADDRESS_STREET_RE.search(content_norm):
        return False
    if venue_norm in content_norm or content_norm in venue_norm:
        return True
    venue_words = [w for w in venue_norm.split() if len(w) > 2]
    if not venue_words:
        venue_words = venue_norm.split()
    matches = sum(1 for w in venue_words if w in content_norm)
    return matches >= max(2, len(venue_words) // 2 + 1)


def inject_canonical_event_text(
    layout: LayoutSpec,
    venue: str,
    *,
    band: str = "",
    event: Optional[Any] = None,
) -> LayoutSpec:
    """Replace LLM venue spellings with the exact calendar venue string."""
    canonical_venue = venue
    new_elements: list[TextElement] = []
    for text in layout.text_elements:
        if _looks_like_venue_text(text.content, canonical_venue):
            display = canonical_venue.upper() if text.all_caps else canonical_venue
            new_elements.append(
                TextElement(
                    content=display,
                    x=text.x,
                    y=text.y,
                    width=text.width,
                    font_size=text.font_size,
                    font_family=text.font_family,
                    font_weight=text.font_weight,
                    color=text.color,
                    alignment=text.alignment,
                    rotation=text.rotation,
                    letter_spacing=text.letter_spacing,
                    line_height=text.line_height,
                    all_caps=text.all_caps,
                )
            )
        else:
            new_elements.append(text)
    layout.text_elements = new_elements
    return layout


def sanitize_band_photo_frame(layout: LayoutSpec) -> LayoutSpec:
    """Disable halftone on band photos — preserves face detail in structured mode."""
    if layout.photo_frame.halftone:
        layout.photo_frame.halftone = False
    return layout


def _hex_luminance(hex_color: str) -> float:
    """Perceived luminance for contrast decisions (0–255)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _apply_footer_contrast(layout: LayoutSpec) -> LayoutSpec:
    """Light footer text on dark backgrounds (fixes navy-on-black address bug)."""
    if _hex_luminance(layout.background.color.hex) >= 140:
        return layout

    light = "#F5F0E6"
    footer_threshold = _footer_y_start(layout.canvas_height) - 4
    updated: list[TextElement] = []
    for text in layout.text_elements:
        in_footer = text.y >= footer_threshold or bool(ADDRESS_ZIP_RE.search(text.content))
        if in_footer and _hex_luminance(text.color.hex) < 140:
            text = TextElement(
                content=text.content,
                x=text.x,
                y=text.y,
                width=text.width,
                font_size=text.font_size,
                font_family=text.font_family,
                font_weight=text.font_weight,
                color=ColorSpec(light),
                alignment=text.alignment,
                rotation=text.rotation,
                letter_spacing=text.letter_spacing,
                line_height=text.line_height,
                all_caps=text.all_caps,
            )
        updated.append(text)
    layout.text_elements = updated
    return layout


def finalize_layout_spec(
    layout: LayoutSpec,
    venue: str,
    band: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
) -> LayoutSpec:
    """Post-process AI layout: canonical text, safe photo frame, mandatory footer."""
    layout = inject_canonical_event_text(layout, venue, band=band, event=event)
    layout = sanitize_band_photo_frame(layout)
    if event is not None:
        layout = ensure_prominent_date_time(layout, event, time)
    layout = ensure_footer_elements(
        layout,
        venue,
        band,
        time,
        address=address,
        event=event,
    )
    layout = _prune_redundant_text_duplicates(layout, venue, band, time, event=event)
    layout = _normalize_footer_positions(layout)
    layout = _apply_footer_contrast(layout)
    from structured_layout.design_system import apply_pro_polish  # noqa: PLC0415

    layout = apply_pro_polish(layout)
    layout = enforce_no_text_on_photo(layout)
    layout = _clamp_all_text_elements(layout)
    return layout


def _clamp_all_text_elements(layout: LayoutSpec) -> LayoutSpec:
    """Enforce max width and safe horizontal placement on every text element."""
    layout.text_elements = [
        clamp_text_element(text, layout) for text in layout.text_elements
    ]
    return layout


def _safe_y_pct(canvas_height: int = 1536) -> float:
    """Minimum y% for text below top safe margin."""
    return round(SAFE_MARGIN_PX / canvas_height * 100, 1)


def _footer_y_start(canvas_height: int = 1536) -> float:
    """y% for footer block above bottom safe margin."""
    return round((canvas_height - SAFE_MARGIN_PX * 4) / canvas_height * 100, 1)


def _has_event_date(text: str, event: Any) -> bool:
    month = event.event_date.strftime("%B").lower()
    day = str(event.event_date.day)
    year = str(event.event_date.year)
    lower = text.lower()
    return month in lower and day in lower and year in lower


def _layout_has_starburst_date(layout: LayoutSpec) -> bool:
    """True when a starburst graphic carries the compact date badge."""
    return any(g.element_type == "starburst" for g in layout.graphic_elements)


def _inject_time_below_photo(
    layout: LayoutSpec,
    time: str,
    *,
    font_size: int = 32,
) -> LayoutSpec:
    """Add time text in the body zone below the photo."""
    photo_bottom = layout.photo_frame.y + layout.photo_frame.height
    y_slot = round(photo_bottom + VERTICAL_GAP_PCT, 1)
    layout.text_elements.append(
        TextElement(
            content=time,
            x=5,
            y=y_slot,
            width=90,
            font_size=font_size,
            font_weight=FontWeight.NORMAL,
            alignment=TextAlignment.CENTER,
        )
    )
    return layout


def ensure_prominent_date_time(
    layout: LayoutSpec,
    event: Any,
    time: str,
) -> LayoutSpec:
    """Inject date/time below the photo when missing or misplaced."""
    layout = relocate_event_details_below_photo(layout, event, time)
    all_text = " ".join(t.content for t in layout.text_elements)
    has_starburst = _layout_has_starburst_date(layout)

    if has_starburst and _has_event_date(all_text, event):
        return layout

    if has_starburst:
        if time and time.lower() not in all_text.lower():
            layout = _inject_time_below_photo(layout, time)
        return layout

    if _has_event_date(all_text, event):
        return layout

    date_str = event.event_date.strftime("%A, %B %d, %Y")
    photo_bottom = layout.photo_frame.y + layout.photo_frame.height
    y_slot = round(photo_bottom + VERTICAL_GAP_PCT, 1)

    new_elements = [
        TextElement(
            content=date_str,
            x=5,
            y=y_slot,
            width=90,
            font_size=40,
            font_weight=FontWeight.BOLD,
            alignment=TextAlignment.CENTER,
        ),
    ]
    if time and time.lower() not in all_text.lower():
        new_elements.append(
            TextElement(
                content=time,
                x=5,
                y=y_slot + VERTICAL_GAP_PCT + 2,
                width=90,
                font_size=32,
                font_weight=FontWeight.NORMAL,
                alignment=TextAlignment.CENTER,
            )
        )

    footer_threshold = _footer_y_start(layout.canvas_height) - 2
    insert_at = next(
        (i for i, t in enumerate(layout.text_elements) if t.y >= footer_threshold),
        len(layout.text_elements),
    )
    layout.text_elements = (
        layout.text_elements[:insert_at] + new_elements + layout.text_elements[insert_at:]
    )
    return layout


def _text_zone(text: TextElement, layout: LayoutSpec) -> str:
    """Classify vertical zone: headline (above photo), body, or footer."""
    photo_top = layout.photo_frame.y
    photo_bottom = layout.photo_frame.y + layout.photo_frame.height
    footer_start = _footer_y_start(layout.canvas_height) - 4

    if ADDRESS_ZIP_RE.search(text.content) or ADDRESS_STREET_RE.search(text.content):
        return "footer"
    if text.y >= footer_start:
        return "footer"
    if text.y < photo_top - 1:
        return "headline"
    if text.y <= photo_bottom + 2:
        return "body"
    return "body"


def _looks_like_featuring_line(content: str, band: str) -> bool:
    lower = content.lower()
    return "featuring" in lower and band.lower() in lower


def _looks_like_band_only(content: str, band: str) -> bool:
    lower = content.lower()
    if "featuring" in lower:
        return False
    band_lower = band.lower()
    return band_lower in lower and len(content.strip()) <= len(band) + 8


def _looks_like_time_text(content: str, time: str) -> bool:
    if not time:
        return False
    lower = content.lower().strip()
    if MONTH_NAME_RE.search(lower) or YEAR_RE.search(lower):
        return False
    return time.lower() in lower and len(content.strip()) <= 20


def _classify_text_role(
    content: str,
    venue: str,
    band: str,
    time: str,
) -> str:
    """Map text content to a dedup role."""
    lower = content.lower()
    if _looks_like_venue_text(content, venue):
        return "venue"
    if _looks_like_featuring_line(content, band):
        return "featuring"
    if _looks_like_band_only(content, band):
        return "band"
    if MONTH_NAME_RE.search(lower) and YEAR_RE.search(lower):
        return "date"
    if _looks_like_time_text(content, time):
        return "time"
    if ADDRESS_ZIP_RE.search(content) or ADDRESS_STREET_RE.search(content):
        return "address"
    return "other"


def _prune_redundant_text_duplicates(
    layout: LayoutSpec,
    venue: str,
    band: str,
    time: str,
    *,
    event: Optional[Any] = None,
) -> LayoutSpec:
    """Keep each event fact once in logical hierarchy (header → body → footer)."""
    house = is_house_series_gig(event) if event is not None else False
    seen: dict[str, bool] = {
        "venue": False,
        "featuring": False,
        "band": False,
        "date": False,
        "time": False,
        "address": False,
    }
    kept: list[TextElement] = []

    for text in sorted(layout.text_elements, key=lambda t: (t.y, t.x)):
        role = _classify_text_role(text.content, venue, band, time)
        zone = _text_zone(text, layout)

        if role == "venue":
            if seen["venue"]:
                continue
            seen["venue"] = True
        elif role == "featuring":
            if seen["featuring"]:
                continue
            seen["featuring"] = True
            seen["band"] = True
        elif role == "band":
            if house and (seen["featuring"] or seen["band"]):
                continue
            if seen["band"]:
                continue
            seen["band"] = True
        elif role == "date":
            if seen["date"]:
                continue
            seen["date"] = True
        elif role == "time":
            if seen["time"]:
                continue
            seen["time"] = True
        elif role == "address":
            if seen["address"]:
                continue
            if house and zone == "footer" and seen["venue"] and seen["featuring"]:
                pass
            seen["address"] = True
        elif house and zone == "footer" and (
            _looks_like_featuring_line(text.content, band)
            or _looks_like_band_only(text.content, band)
            or _looks_like_venue_text(text.content, venue)
        ):
            continue

        kept.append(text)

    layout.text_elements = sorted(kept, key=lambda t: (t.y, t.x))
    return layout


def relocate_event_details_below_photo(
    layout: LayoutSpec,
    event: Any,
    time: str,
) -> LayoutSpec:
    """Move date/time only when they overlap the photo frame."""
    from structured_layout.layout_geometry import text_overlaps_photo

    photo_bottom = layout.photo_frame.y + layout.photo_frame.height

    date_elem: Optional[TextElement] = None
    time_elem: Optional[TextElement] = None
    kept: list[TextElement] = []
    for text in layout.text_elements:
        lower = text.content.lower()
        is_date = bool(MONTH_NAME_RE.search(lower) and YEAR_RE.search(lower))
        is_time = bool(
            time
            and time.lower() in lower
            and len(text.content.strip()) <= 16
            and not is_date
        )
        if is_date:
            if text_overlaps_photo(text, layout):
                date_elem = text
                continue
            kept.append(text)
            continue
        if is_time:
            if text_overlaps_photo(text, layout):
                time_elem = text
                continue
            kept.append(text)
            continue
        kept.append(text)

    layout.text_elements = kept
    y = round(photo_bottom + VERTICAL_GAP_PCT, 1)
    if date_elem:
        layout.text_elements.append(
            TextElement(
                content=date_elem.content,
                x=5,
                y=y,
                width=90,
                font_size=min(40, date_elem.font_size),
                font_weight=FontWeight.BOLD,
                alignment=TextAlignment.CENTER,
            )
        )
        y += VERTICAL_GAP_PCT + 2
    if time_elem:
        layout.text_elements.append(
            TextElement(
                content=time_elem.content,
                x=5,
                y=y,
                width=90,
                font_size=min(32, time_elem.font_size),
                font_weight=FontWeight.NORMAL,
                alignment=TextAlignment.CENTER,
            )
        )
    return layout


def _normalize_footer_positions(layout: LayoutSpec) -> LayoutSpec:
    """Re-stack footer-zone text inside safe margins without overlap."""
    canvas_h = layout.canvas_height
    max_y = round((canvas_h - SAFE_MARGIN_PX - 24) / canvas_h * 100, 1)
    footer_threshold = _footer_y_start(canvas_h) - 4

    footer_indices = [
        i
        for i, t in enumerate(layout.text_elements)
        if t.y >= footer_threshold or ADDRESS_ZIP_RE.search(t.content)
    ]
    if not footer_indices:
        return layout

    min_line_gap = VERTICAL_GAP_PCT + 0.8

    # Compute total height needed using per-element font size
    def _el_height_pct(t: TextElement) -> float:
        return round(t.font_size * t.line_height / canvas_h * 100 + min_line_gap, 1)

    total_needed = sum(_el_height_pct(layout.text_elements[i]) for i in footer_indices)
    y = max(
        min(_footer_y_start(canvas_h), max_y - total_needed),
        _footer_y_start(canvas_h) - 8,
    )
    for idx in footer_indices:
        text = layout.text_elements[idx]
        layout.text_elements[idx] = TextElement(
            content=text.content,
            x=max(5.0, text.x),
            y=min(y, max_y),
            width=min(90.0, text.width),
            font_size=text.font_size,
            font_family=text.font_family,
            font_weight=text.font_weight,
            color=text.color,
            alignment=text.alignment,
            rotation=text.rotation,
            letter_spacing=text.letter_spacing,
            line_height=text.line_height,
            all_caps=text.all_caps,
        )
        y += _el_height_pct(text)
    return layout


def _layout_has_text_role(
    layout: LayoutSpec,
    role: str,
    venue: str,
    band: str,
    time: str,
) -> bool:
    return any(
        _classify_text_role(t.content, venue, band, time) == role
        for t in layout.text_elements
    )


def ensure_footer_elements(
    layout: LayoutSpec,
    venue: str,
    band: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
) -> LayoutSpec:
    """Inject only missing footer pieces — never duplicate header/body facts."""
    house = is_house_series_gig(event) if event is not None else False
    has_venue = _layout_has_text_role(layout, "venue", venue, band, time)
    has_featuring = _layout_has_text_role(layout, "featuring", venue, band, time)
    has_band = _layout_has_text_role(layout, "band", venue, band, time)
    has_address = _layout_has_text_role(layout, "address", venue, band, time)

    footer_y = _footer_y_start(layout.canvas_height)
    line_gap = VERTICAL_GAP_PCT + 1.5
    footer_elements: list[TextElement] = []

    if house:
        if not has_address and address:
            footer_elements.append(
                TextElement(
                    content=address,
                    x=5,
                    y=footer_y,
                    width=90,
                    font_size=20,
                    font_weight=FontWeight.NORMAL,
                    alignment=TextAlignment.CENTER,
                )
            )
            footer_y += line_gap
        if not has_venue and not has_featuring:
            footer_elements.append(
                TextElement(
                    content=venue,
                    x=5,
                    y=footer_y,
                    width=90,
                    font_size=24,
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.CENTER,
                )
            )
            footer_y += line_gap
            if not has_band:
                footer_elements.append(
                    TextElement(
                        content=featured_act_line(band),
                        x=5,
                        y=footer_y,
                        width=90,
                        font_size=28,
                        font_weight=FontWeight.BOLD,
                        alignment=TextAlignment.CENTER,
                    )
                )
    else:
        if not has_venue:
            footer_elements.append(
                TextElement(
                    content=venue,
                    x=5,
                    y=footer_y,
                    width=90,
                    font_size=24,
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.CENTER,
                )
            )
            footer_y += line_gap
        if not has_address and address:
            footer_elements.append(
                TextElement(
                    content=address,
                    x=5,
                    y=footer_y,
                    width=90,
                    font_size=20,
                    font_weight=FontWeight.NORMAL,
                    alignment=TextAlignment.CENTER,
                )
            )
            footer_y += line_gap
        if not has_band and not has_featuring:
            footer_elements.append(
                TextElement(
                    content=band,
                    x=5,
                    y=footer_y,
                    width=90,
                    font_size=28,
                    font_weight=FontWeight.BOLD,
                    alignment=TextAlignment.CENTER,
                )
            )

    layout.text_elements = layout.text_elements + footer_elements
    return layout


def create_default_handbill_layout(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
) -> LayoutSpec:
    from structured_layout.fixed_templates import create_handbill_layout

    return create_handbill_layout(venue, band, date, time, address=address, event=event)


def create_default_collage_layout(
    venue: str,
    band: str,
    date: str,
    time: str,
    *,
    address: str = "",
    event: Optional[Any] = None,
) -> LayoutSpec:
    from structured_layout.fixed_templates import create_collage_layout

    return create_collage_layout(venue, band, date, time, address=address, event=event)
