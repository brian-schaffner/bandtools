"""Register web routes with optional Tailscale path prefix (/flyers)."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from bridge.review import root_path

F = TypeVar("F", bound=Callable[..., Any])


def public_paths(path: str) -> tuple[str, ...]:
    """Paths to register: bare + prefixed when ROOT_PATH/BRIDGE_PUBLIC_URL implies /flyers."""
    prefix = root_path()
    if path == "/":
        if prefix:
            return ("/", prefix, f"{prefix}/")
        return ("/",)
    if prefix:
        return (path, f"{prefix}{path}")
    return (path,)


def add_get(app: Any, path: str, **kwargs: Any) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        for route_path in public_paths(path):
            app.get(route_path, **kwargs)(func)
        return func

    return decorator


def add_post(app: Any, path: str, **kwargs: Any) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        for route_path in public_paths(path):
            app.post(route_path, **kwargs)(func)
        return func

    return decorator
