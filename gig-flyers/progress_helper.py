"""Shared progress callback helper for generation pipelines."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

ProgressCallback = Callable[..., None]


def emit_progress(
    on_progress: Optional[ProgressCallback],
    *,
    step: str,
    substep: str = "",
    message: str = "",
    detail: str = "",
    progress: int = 0,
    option: str = "",
    attempt: int = 0,
    log: bool = True,
    option_phase: str = "",
    option_progress: Optional[int] = None,
    option_note: str = "",
    option_image_url: str = "",
    option_exhausted: Optional[bool] = None,
    provider_label: str = "",
    active_provider: str = "",
) -> None:
    if not on_progress:
        return
    try:
        kwargs = dict(
            step=step,
            substep=substep,
            message=message,
            detail=detail,
            progress=progress,
            option=option,
            attempt=attempt,
            log=log,
        )
        if option_phase:
            kwargs["option_phase"] = option_phase
        if option_progress is not None:
            kwargs["option_progress"] = option_progress
        if option_note:
            kwargs["option_note"] = option_note
        if option_image_url:
            kwargs["option_image_url"] = option_image_url
        if option_exhausted is not None:
            kwargs["option_exhausted"] = option_exhausted
        if provider_label:
            kwargs["provider_label"] = provider_label
        if active_provider:
            kwargs["active_provider"] = active_provider
        on_progress(**kwargs)
    except TypeError:
        on_progress(step, message or detail or substep, progress)


@contextmanager
def heartbeat_during(
    on_progress: Optional[ProgressCallback],
    *,
    step: str,
    message_template: str,
    progress: int = 0,
    option: str = "",
    attempt: int = 0,
    interval: float = 1.0,
    progress_start: Optional[int] = None,
    progress_end: Optional[int] = None,
    estimated_seconds: Optional[float] = None,
    option_phase: str = "",
) -> Iterator[None]:
    """Emit heartbeat progress every `interval` seconds during a blocking call."""
    if not on_progress:
        yield
        return

    stop = threading.Event()

    def _loop() -> None:
        seconds = 0
        while not stop.wait(interval):
            seconds += int(interval)
            emit_progress(
                on_progress,
                step=step,
                substep="heartbeat",
                message=message_template.format(seconds=seconds, option=option or "?"),
                progress=progress,
                option=option,
                attempt=attempt,
                log=False,
            )

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=0.2)
