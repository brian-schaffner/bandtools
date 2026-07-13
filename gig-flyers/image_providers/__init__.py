"""Image generation providers (OpenAI, Gemini).

This module also exports photo treatment constants and utilities that enforce
the doctrine: band photos are SOURCE ARTWORK, never regenerated or reinterpreted.
"""

from image_providers.base import (
    generate_band_replace_with_fallback,
    generate_with_fallback,
    get_image_provider,
    is_provider_split_enabled,
    resolve_image_provider,
    resolve_image_provider_for_option,
    resolve_provider_map,
)
from image_providers.photo_treatment import (
    PHOTO_ALLOWED,
    PHOTO_FORBIDDEN,
    get_photo_treatment_doctrine,
    photo_treatment_prompt_block,
)
from image_providers.typography_compose import typography_only_enabled

__all__ = [
    "generate_band_replace_with_fallback",
    "generate_with_fallback",
    "get_image_provider",
    "is_provider_split_enabled",
    "resolve_image_provider",
    "resolve_image_provider_for_option",
    "resolve_provider_map",
    "PHOTO_ALLOWED",
    "PHOTO_FORBIDDEN",
    "get_photo_treatment_doctrine",
    "photo_treatment_prompt_block",
    "typography_only_enabled",
]
