"""Shared OpenAI images.edit helper for shell pipeline steps."""

from __future__ import annotations

from typing import Any, BinaryIO, Callable, Callable

from shell_model_policy import ShellModelChoice


def shell_images_edit(
    client: Any,
    *,
    image: BinaryIO,
    prompt: str,
    choice: ShellModelChoice,
    mask: BinaryIO | None = None,
    on_call: Callable[[], None] | None = None,
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
    result = client.images.edit(**kwargs)
    if on_call is not None:
        on_call()
    return result
