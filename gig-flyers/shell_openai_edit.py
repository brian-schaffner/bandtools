"""Shared OpenAI images.edit helper for shell pipeline steps."""

from __future__ import annotations

from typing import Any, BinaryIO

from shell_model_policy import ShellModelChoice


def shell_images_edit(
    client: Any,
    *,
    image: BinaryIO,
    prompt: str,
    choice: ShellModelChoice,
    mask: BinaryIO | None = None,
) -> Any:
    kwargs: dict[str, Any] = {
        "model": choice.model,
        "image": image,
        "prompt": prompt,
        "size": choice.size,
        "quality": choice.quality,
        "n": 1,
    }
    if mask is not None:
        kwargs["mask"] = mask
    if choice.input_fidelity:
        kwargs["input_fidelity"] = choice.input_fidelity
    return client.images.edit(**kwargs)
