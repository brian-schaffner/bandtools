"""Flyer Agent FastAPI routes."""

from __future__ import annotations

import asyncio
import os
from functools import partial
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bridge.job_status import complete_job, fail_job, is_job_active, report_progress, start_job
from bridge.review import band_tools_home_path, route_path
from bridge.routing import add_get, add_post
from flyer_agent.agent import FlyerAgent
from flyer_agent.auth import extract_session_token, require_agent_user, user_to_dict, validate_session
from flyer_agent.ui import (
    render_agent_dashboard,
    render_catalog_page,
    render_generating_page,
    render_gig_detail_page,
    render_login_page,
    render_research_page,
)
from gig_calendar import CalendarUnavailableError, find_gig_by_id
from state import append_feedback, get_gig_state, upsert_gig

_agent = FlyerAgent()
_generate_in_flight: set[str] = set()


def _band_tools_url() -> str:
    return os.getenv("BAND_TOOLS_URL", band_tools_home_path()).rstrip("/")


def _progress_callback(gig_id: str):
    def callback(**kwargs: Any) -> None:
        report_progress(gig_id, **kwargs)

    return callback


async def _run_agent_job(gig_id: str, job_type: str, runner) -> None:
    record = get_gig_state(gig_id) or {}
    event = record.get("event") or {}
    title = f"{event.get('short_date') or event.get('date', '')} @ {event.get('venue', 'Venue')}".strip()
    if not is_job_active(gig_id):
        start_job(gig_id, job_type, title=title, detail=f"Flyer Agent {job_type}")
    try:
        await asyncio.to_thread(runner)
        complete_job(gig_id, "Done")
    except Exception as exc:  # noqa: BLE001
        fail_job(gig_id, str(exc))
    finally:
        _generate_in_flight.discard(gig_id)


def register_agent_routes(app: FastAPI) -> None:
    """Register Flyer Agent routes (bare + /flyers prefix via routing helpers)."""

    @add_get(app, "/agent/login", response_class=HTMLResponse)
    async def agent_login_page() -> HTMLResponse:
        return HTMLResponse(render_login_page(band_tools_url=_band_tools_url()))

    @add_get(app, "/agent/api/session")
    async def agent_session_api(request: Request) -> JSONResponse:
        user = await validate_session(extract_session_token(request))
        if not user:
            return JSONResponse({"authenticated": False})
        return JSONResponse({"authenticated": True, "user": user_to_dict(user)})

    @add_get(app, "/agent/api/gigs")
    async def agent_gigs_api(request: Request) -> JSONResponse:
        await require_agent_user(request)
        try:
            board = _agent.gig_board()
        except CalendarUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return JSONResponse(board)

    @add_get(app, "/agent", response_class=HTMLResponse)
    async def agent_dashboard(request: Request) -> HTMLResponse:
        user = await validate_session(extract_session_token(request))
        if not user:
            return RedirectResponse(route_path("/agent/login"), status_code=302)
        try:
            board = _agent.gig_board()
        except CalendarUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return HTMLResponse(
            render_agent_dashboard(
                user=user_to_dict(user),
                board=board,
                system=_agent.system_context(),
            )
        )

    @add_get(app, "/agent/gig/{gig_id}", response_class=HTMLResponse)
    async def agent_gig_page(gig_id: str, request: Request) -> HTMLResponse:
        user = await validate_session(extract_session_token(request))
        if not user:
            return RedirectResponse(route_path("/agent/login"), status_code=302)
        detail = _agent.gig_detail(gig_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Gig not found")
        return HTMLResponse(
            render_gig_detail_page(
                user=user_to_dict(user),
                detail=detail,
                recommendation=_agent.recommend_action(gig_id),
            )
        )

    @add_post(app, "/agent/gig/{gig_id}/generate")
    async def agent_generate(gig_id: str, request: Request) -> HTMLResponse:
        await require_agent_user(request)
        if gig_id in _generate_in_flight:
            event = (get_gig_state(gig_id) or {}).get("event") or {}
            return HTMLResponse(render_generating_page(gig_id, event))

        event_obj = find_gig_by_id(gig_id)
        if not event_obj:
            raise HTTPException(status_code=404, detail="Gig not found")
        upsert_gig(gig_id, event=event_obj.to_dict())
        _generate_in_flight.add(gig_id)
        event = event_obj.to_dict()
        title = f"{event.get('short_date')} @ {event.get('venue')}"
        start_job(gig_id, "generate", title=title, detail="Flyer Agent generation")
        asyncio.create_task(
            _run_agent_job(
                gig_id,
                "generate",
                partial(_agent.generate, gig_id, on_progress=_progress_callback(gig_id)),
            )
        )
        return HTMLResponse(render_generating_page(gig_id, event))

    @add_post(app, "/agent/gig/{gig_id}/regenerate")
    async def agent_regenerate_route(gig_id: str, request: Request) -> HTMLResponse:
        await require_agent_user(request)
        detail = _agent.gig_detail(gig_id)
        if not detail or not detail.get("can_regenerate"):
            raise HTTPException(status_code=409, detail="Cannot regenerate this gig")
        append_feedback(gig_id, "regenerate", "", "", "REGENERATE (Flyer Agent)")
        _generate_in_flight.add(gig_id)
        event = detail.get("event") or {}
        start_job(
            gig_id,
            "regenerate",
            title=f"{event.get('short_date')} @ {event.get('venue')}",
            detail="Agent regenerate",
        )
        asyncio.create_task(
            _run_agent_job(
                gig_id,
                "regenerate",
                partial(_agent.regenerate, gig_id, on_progress=_progress_callback(gig_id)),
            )
        )
        return HTMLResponse(render_generating_page(gig_id, event))

    @add_post(app, "/agent/gig/{gig_id}/revise")
    async def agent_revise_route(
        gig_id: str,
        request: Request,
        option: str = Form(...),
        feedback: str = Form(...),
    ) -> RedirectResponse:
        await require_agent_user(request)
        detail = _agent.gig_detail(gig_id)
        if not detail or not detail.get("can_revise"):
            raise HTTPException(status_code=409, detail="Cannot revise this gig")
        append_feedback(gig_id, "revise", option.upper(), feedback, feedback)
        _generate_in_flight.add(gig_id)
        event = detail.get("event") or {}
        start_job(
            gig_id,
            "revise",
            title=f"{event.get('short_date')} @ {event.get('venue')}",
            detail=feedback[:120],
        )
        asyncio.create_task(
            _run_agent_job(
                gig_id,
                "revise",
                partial(
                    _agent.revise,
                    gig_id,
                    option=option,
                    feedback=feedback,
                    on_progress=_progress_callback(gig_id),
                ),
            )
        )
        return RedirectResponse(route_path(f"/agent/gig/{gig_id}"), status_code=303)

    @add_get(app, "/agent/catalog", response_class=HTMLResponse)
    async def agent_catalog_page(request: Request) -> HTMLResponse:
        await require_agent_user(request)
        return HTMLResponse(render_catalog_page(_agent.catalog(limit=50)))

    @add_get(app, "/agent/research", response_class=HTMLResponse)
    async def agent_research_page(request: Request) -> HTMLResponse:
        await require_agent_user(request)
        return HTMLResponse(render_research_page(_agent.design_research(limit=30)))

    @add_post(app, "/agent/research/refresh")
    async def agent_research_refresh(request: Request) -> RedirectResponse:
        await require_agent_user(request)
        use_llm = os.getenv("GIG_RESEARCH_USE_LLM", "").strip().lower() in {"1", "true", "yes"}
        await asyncio.to_thread(_agent.refresh_research, use_llm=use_llm)
        return RedirectResponse(route_path("/agent/research"), status_code=303)
