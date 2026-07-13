"""Flyer Agent orchestrator — plans and executes flyer design workflows."""

from __future__ import annotations

from typing import Any, Optional

from flyer_agent.actions import agent_approve, agent_generate, agent_regenerate, agent_revise
from flyer_agent.catalog import load_design_catalog, sync_approved_flyers_to_catalog
from flyer_agent.context import agent_system_context, gig_agent_context
from flyer_agent.gig_board import build_agent_gig_board, build_gig_detail
from flyer_agent.research_worker import load_design_research, run_design_research
from gig_calendar import find_gig_by_id


class FlyerAgent:
    """Expert concert-poster agent built on existing gig-flyers modules."""

    def system_context(self) -> dict[str, Any]:
        return agent_system_context()

    def gig_board(self, *, max_days: int = 60) -> dict[str, Any]:
        return build_agent_gig_board(max_days=max_days)

    def gig_detail(self, gig_id: str) -> Optional[dict[str, Any]]:
        return build_gig_detail(gig_id)

    def gig_context(self, gig_id: str) -> dict[str, Any]:
        event = find_gig_by_id(gig_id)
        if not event:
            raise ValueError(f"Unknown gig: {gig_id}")
        return gig_agent_context(event)

    def catalog(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return load_design_catalog(limit=limit)

    def design_research(self, *, limit: int = 10) -> list[dict[str, Any]]:
        return load_design_research(limit=limit)

    def refresh_research(self, *, use_llm: bool = False) -> dict[str, Any]:
        return run_design_research(use_llm=use_llm)

    def sync_catalog_from_approvals(self) -> int:
        return sync_approved_flyers_to_catalog()

    def generate(self, gig_id: str, *, on_progress: Optional[Any] = None) -> dict[str, Any]:
        return agent_generate(gig_id, on_progress=on_progress)

    def regenerate(self, gig_id: str, *, on_progress: Optional[Any] = None) -> dict[str, Any]:
        return agent_regenerate(gig_id, on_progress=on_progress)

    def revise(
        self,
        gig_id: str,
        *,
        option: str,
        feedback: str,
        on_progress: Optional[Any] = None,
    ) -> dict[str, Any]:
        return agent_revise(gig_id, option=option, feedback=feedback, on_progress=on_progress)

    def approve(self, gig_id: str, *, option: str) -> dict[str, Any]:
        return agent_approve(gig_id, option=option)

    def recommend_action(self, gig_id: str) -> dict[str, Any]:
        detail = self.gig_detail(gig_id)
        if not detail:
            return {"action": "unknown", "message": "Gig not found"}

        if detail.get("workflow") == "approved":
            return {
                "action": "view",
                "message": "This gig has an approved flyer. Regenerate for a fresh round.",
            }
        if detail.get("can_revise"):
            return {
                "action": "revise_or_approve",
                "message": "Review the options below — approve one or revise with feedback.",
            }
        if detail.get("can_generate"):
            return {
                "action": "generate",
                "message": "No flyers yet. Generate 3 options tailored to this venue and date.",
            }
        if detail.get("can_regenerate"):
            return {
                "action": "regenerate",
                "message": "Flyers exist from a prior round. Regenerate for fresh options.",
            }
        return {"action": "wait", "message": "Generation may be in progress."}
