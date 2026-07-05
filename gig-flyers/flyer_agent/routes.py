"""Flyer Agent FastAPI routes."""

from __future__ import annotations

import asyncio
import os
from functools import partial
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from bridge.job_status import complete_job, fail_job, get_job_status, is_job_active, report_progress, start_job
from bridge.review import band_tools_home_path, route_path
from bridge.routing import add_get, add_post
from flyer_agent.agent import FlyerAgent
from flyer_agent.chat import agent_chat_reply
from flyer_agent.urls import flyer_asset_url
from flyer_agent.auth import extract_session_token, require_agent_user, user_to_dict, validate_session
from flyer_agent.ui import (
    render_agent_dashboard,
    render_catalog_page,
    render_generating_page,
    render_gig_detail_page,
    render_login_page,
    render_research_page,
)
from flyer_agent.session_sync import render_session_bootstrap
from gig_calendar import CalendarUnavailableError, find_gig_by_id
from state import append_feedback, get_gig_state, upsert_gig

_agent = FlyerAgent()
_generate_in_flight: set[str] = set()


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    gig_id: str | None = None


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


def _job_in_flight(gig_id: str) -> bool:
    return gig_id in _generate_in_flight or is_job_active(gig_id)


def _gig_detail_payload(gig_id: str) -> dict[str, Any]:
    detail = _agent.gig_detail(gig_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Gig not found")
    round_num = int(detail.get("round") or 0)
    updated_at = str(detail.get("updated_at") or "")
    flyers = []
    for flyer in detail.get("flyers") or []:
        flyers.append(
            {
                **flyer,
                "url": flyer_asset_url(flyer["path"], round_num=round_num, updated_at=updated_at),
            }
        )
    payload = {**detail, "flyers": flyers}
    return {
        "detail": payload,
        "recommendation": _agent.recommend_action(gig_id),
    }


def _start_agent_job(
    gig_id: str,
    job_type: str,
    *,
    runner,
    detail: str = "",
) -> dict[str, Any]:
    if _job_in_flight(gig_id):
        active = get_job_status(gig_id)
        return {
            "started": False,
            "reason": "in_flight",
            "type": active.get("job_type") or job_type,
            "status": active.get("status") or "running",
            "message": active.get("message") or "A job is already running for this gig.",
        }

    record = get_gig_state(gig_id) or {}
    event = record.get("event") or {}
    title = f"{event.get('short_date') or event.get('date', '')} @ {event.get('venue', 'Venue')}".strip()
    _generate_in_flight.add(gig_id)
    start_job(gig_id, job_type, title=title, detail=detail or f"Flyer Agent {job_type}")
    asyncio.create_task(_run_agent_job(gig_id, job_type, runner))
    return {
        "started": True,
        "type": job_type,
        "status": "running",
        "gig_id": gig_id,
    }


async def _execute_chat_action(gig_id: str, execution: dict[str, Any]) -> dict[str, Any]:
    job_type = execution["type"]
    detail = _agent.gig_detail(gig_id)
    if not detail:
        return {"started": False, "reason": "not_found", "type": job_type}

    if job_type == "generate":
        if not detail.get("can_generate"):
            return {"started": False, "reason": "not_allowed", "type": job_type}
        event_obj = find_gig_by_id(gig_id)
        if not event_obj:
            return {"started": False, "reason": "not_found", "type": job_type}
        upsert_gig(gig_id, event=event_obj.to_dict())
        job = _start_agent_job(
            gig_id,
            "generate",
            runner=partial(_agent.generate, gig_id, on_progress=_progress_callback(gig_id)),
            detail="Flyer Agent generation (chat)",
        )
        job["expected_round"] = max(int(detail.get("round") or 0), 1)
        return job

    if job_type == "regenerate":
        if not detail.get("can_regenerate"):
            return {"started": False, "reason": "not_allowed", "type": job_type}
        append_feedback(gig_id, "regenerate", "", "", "REGENERATE (Flyer Agent chat)")
        job = _start_agent_job(
            gig_id,
            "regenerate",
            runner=partial(_agent.regenerate, gig_id, on_progress=_progress_callback(gig_id)),
            detail="Agent regenerate (chat)",
        )
        job["expected_round"] = int(detail.get("round") or 0) + 1
        return job

    if job_type == "revise":
        if not detail.get("can_revise"):
            return {"started": False, "reason": "not_allowed", "type": job_type}
        option = execution["option"]
        feedback = execution["feedback"]
        append_feedback(gig_id, "revise", option, feedback, feedback)
        job = _start_agent_job(
            gig_id,
            "revise",
            runner=partial(
                _agent.revise,
                gig_id,
                option=option,
                feedback=feedback,
                on_progress=_progress_callback(gig_id),
            ),
            detail=feedback[:120],
        )
        job["option"] = option
        job["feedback"] = feedback
        job["expected_round"] = int(detail.get("round") or 0) + 1
        return job

    return {"started": False, "reason": "unknown", "type": job_type}


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

    @add_post(app, "/agent/api/chat")
    async def agent_chat_api(request: Request, body: AgentChatRequest) -> JSONResponse:
        await require_agent_user(request)
        result = agent_chat_reply(body.message, gig_id=body.gig_id, agent=_agent)
        execution = result.get("execution")
        if execution and body.gig_id:
            job = await _execute_chat_action(body.gig_id, execution)
            result["job"] = job
            if not job.get("started"):
                reason = job.get("reason")
                if reason == "in_flight":
                    result["reply"] += (
                        f"\n\nNote: a {job.get('type', 'generation')} job is already running — "
                        "I'll update you when it finishes."
                    )
                elif reason == "not_allowed":
                    result["reply"] += "\n\nThat action isn't available for this gig right now."
        return JSONResponse(result)

    @add_get(app, "/agent/api/gig/{gig_id}/job")
    async def agent_gig_job_api(gig_id: str, request: Request) -> JSONResponse:
        await require_agent_user(request)
        return JSONResponse(
            get_job_status(gig_id),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
        )

    @add_get(app, "/agent/api/gig/{gig_id}")
    async def agent_gig_api(gig_id: str, request: Request) -> JSONResponse:
        await require_agent_user(request)
        return JSONResponse(_gig_detail_payload(gig_id))

    @add_get(app, "/agent", response_class=HTMLResponse)
    async def agent_dashboard(request: Request) -> HTMLResponse:
        user = await validate_session(extract_session_token(request))
        if not user:
            return HTMLResponse(render_session_bootstrap(redirect_to=route_path("/agent")))
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
            return HTMLResponse(
                render_session_bootstrap(redirect_to=route_path(f"/agent/gig/{gig_id}"))
            )
        detail = _agent.gig_detail(gig_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Gig not found")
        try:
            board = _agent.gig_board()
        except CalendarUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return HTMLResponse(
            render_gig_detail_page(
                user=user_to_dict(user),
                detail=detail,
                recommendation=_agent.recommend_action(gig_id),
                board=board,
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
        user = await validate_session(extract_session_token(request))
        if not user:
            return HTMLResponse(render_session_bootstrap(redirect_to=route_path("/agent/catalog")))
        return HTMLResponse(render_catalog_page(_agent.catalog(limit=50)))

    @add_get(app, "/agent/research", response_class=HTMLResponse)
    async def agent_research_page(request: Request) -> HTMLResponse:
        user = await validate_session(extract_session_token(request))
        if not user:
            return HTMLResponse(render_session_bootstrap(redirect_to=route_path("/agent/research")))
        return HTMLResponse(render_research_page(_agent.design_research(limit=30)))

    @add_post(app, "/agent/research/refresh")
    async def agent_research_refresh(request: Request) -> RedirectResponse:
        await require_agent_user(request)
        use_llm = os.getenv("GIG_RESEARCH_USE_LLM", "").strip().lower() in {"1", "true", "yes"}
        await asyncio.to_thread(_agent.refresh_research, use_llm=use_llm)
        return RedirectResponse(route_path("/agent/research"), status_code=303)
