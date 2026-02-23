"""Orchestrator instance management API — thin aggregator.

Registers all orchestrator-related routers:
  orchestrator_crud_controller      — CRUD endpoints
  orchestrator_lifecycle_controller — load/unload endpoints
  orchestrator_plugin_controller    — plugin settings endpoints

Schemas and shared helpers are in controller/schemas/orchestrator_schemas.py.
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter

import cadence.controller.orchestrator_crud_controller as orchestrator_crud_controller
import cadence.controller.orchestrator_lifecycle_controller as orchestrator_lifecycle_controller
import cadence.controller.orchestrator_plugin_controller as orchestrator_plugin_controller
from cadence.controller.schemas.orchestrator_schemas import (  # noqa: F401 — re-export for backward compat
    ActivatePluginVersionRequest,
    CreateOrchestratorRequest,
    LoadOrchestratorRequest,
    OrchestratorResponse,
    UpdateOrchestratorConfigRequest,
    UpdateOrchestratorStatusRequest,
    UpdatePluginSettingsRequest,
    validate_orchestrator_access,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["orchestrators"])
router.include_router(orchestrator_crud_controller.router)
router.include_router(orchestrator_lifecycle_controller.router)
router.include_router(orchestrator_plugin_controller.router)

engine_router = APIRouter(prefix="/api/engine", tags=["engine"])


@engine_router.get("/supervisor/prompts")
async def get_supervisor_default_prompts() -> Dict[str, str]:
    """Return default prompt templates for each supervisor node."""
    from cadence.engine.impl.langgraph.supervisor.prompts import SupervisorPrompts

    return {
        "classifier_node": SupervisorPrompts.ROUTER,
        "planner_node": SupervisorPrompts.PLANNER,
        "synthesizer_node": SupervisorPrompts.SYNTHESIZER,
        "validation_node": SupervisorPrompts.VALIDATION,
        "clarifier_node": SupervisorPrompts.CLARIFIER,
        "responder_node": SupervisorPrompts.RESPONDER,
        "error_handler_node": SupervisorPrompts.ERROR_HANDLER,
    }


# Keep the private helper for any existing test references
def _validate_orchestrator_access(
    instance: Optional[Dict],
    instance_id: str,
    org_id: str,
) -> None:
    """Validate instance exists, is not deleted, and belongs to org."""
    validate_orchestrator_access(instance, instance_id, org_id)
