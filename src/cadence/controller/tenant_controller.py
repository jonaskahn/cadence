"""Tenant management API — thin aggregator.

Registers all tenant-related routers:
  organization_controller  — org CRUD + settings
  llm_config_controller    — LLM configs + provider models
  user_controller          — user CRUD
  membership_controller    — org membership

Permission summary:
  /api/orgs                       any authenticated user (role-aware list)
  /api/admin/orgs/*               sys_admin only
  /api/users                      org_admin or sys_admin
  /api/admin/users                sys_admin only
  /api/admin/orgs/{id}/users      sys_admin only
  /api/orgs/{org_id}/settings     org_admin or sys_admin
  /api/orgs/{org_id}/llm-configs  org_admin only (sys_admin excluded — BYOK isolation)
  /api/orgs/{org_id}/members      org_admin or sys_admin
  /api/orgs/{org_id}/users        org_admin or sys_admin
"""

from fastapi import APIRouter

import cadence.controller.llm_config_controller as llm_config_controller
import cadence.controller.membership_controller as membership_controller
import cadence.controller.organization_controller as organization_controller
import cadence.controller.user_controller as user_controller

router = APIRouter(tags=["tenants"])
router.include_router(organization_controller.router)
router.include_router(llm_config_controller.router)
router.include_router(user_controller.router)
router.include_router(membership_controller.router)
