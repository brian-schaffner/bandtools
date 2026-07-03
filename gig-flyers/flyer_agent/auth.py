"""Validate Band Tools Google sessions via the setloader API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from fastapi import HTTPException, Request


@dataclass(frozen=True)
class AgentUser:
    user_id: str
    email: str
    name: str


def _setloader_base_url() -> str:
    return os.getenv("SETLOADER_INTERNAL_URL", "http://127.0.0.1:8002").rstrip("/")


def _api_secret() -> str:
    return os.getenv("NEXT_PUBLIC_API_SECRET") or os.getenv("SECRET") or os.getenv("BRIDGE_SECRET") or "change-me"


def extract_session_token(request: Request) -> Optional[str]:
    """Resolve session token from header, query param, or cookie."""
    header = (request.headers.get("X-Session-ID") or "").strip()
    if header and header != "guest-session":
        return header
    query = (request.query_params.get("session") or "").strip()
    if query:
        return query
    cookie = (request.cookies.get("session_token") or request.cookies.get("session_id") or "").strip()
    if cookie and cookie != "guest-session":
        return cookie
    return None


async def validate_session(session_token: Optional[str]) -> Optional[AgentUser]:
    """Return user when session is valid; None when missing or expired."""
    if not session_token or session_token == "guest-session":
        return None

    url = f"{_setloader_base_url()}/user/status"
    headers = {
        "X-Secret": _api_secret(),
        "X-Session-ID": session_token,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError:
        return None

    if response.status_code != 200:
        return None

    data = response.json()
    if not data.get("authenticated"):
        return None

    email = str(data.get("user_email") or "").strip()
    if not email:
        return None

    user_id = str(data.get("user_id") or email)
    name = email.split("@")[0]
    return AgentUser(user_id=user_id, email=email, name=name)


async def require_agent_user(request: Request) -> AgentUser:
    """FastAPI dependency: authenticated user or 401."""
    user = await validate_session(extract_session_token(request))
    if not user:
        raise HTTPException(status_code=401, detail="Sign in with Google to use Flyer Agent")
    return user


def user_to_dict(user: AgentUser) -> dict[str, Any]:
    return {"user_id": user.user_id, "email": user.email, "name": user.name}
