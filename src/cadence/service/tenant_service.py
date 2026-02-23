"""Tenant service — combined org + user management.

TenantService composes OrganizationServiceMixin and UserServiceMixin,
wiring all repositories in a single __init__.
"""

import logging
from typing import Optional

from cadence.repository.orchestrator_instance_repository import (
    OrchestratorInstanceRepository,
)
from cadence.repository.organization_llm_config_repository import (
    OrganizationLLMConfigRepository,
)
from cadence.repository.organization_repository import OrganizationRepository
from cadence.repository.organization_settings_repository import (
    OrganizationSettingsRepository,
)
from cadence.repository.user_org_membership_repository import (
    UserOrgMembershipRepository,
)
from cadence.repository.user_repository import UserRepository
from cadence.service.organization_service import OrganizationServiceMixin
from cadence.service.user_service import UserServiceMixin

logger = logging.getLogger(__name__)


class TenantService(OrganizationServiceMixin, UserServiceMixin):
    """Service for managing organizations, settings, LLM configs, and users.

    Attributes:
        org_repo: Organization repository
        org_settings_repo: Organization settings repository
        org_llm_config_repo: Organization LLM config repository
        user_repo: User repository
        membership_repo: User-org membership repository
        instance_repo: Orchestrator instance repository (used for LLM in-use checks)
    """

    def __init__(
        self,
        org_repo: OrganizationRepository,
        org_settings_repo: OrganizationSettingsRepository,
        org_llm_config_repo: OrganizationLLMConfigRepository,
        user_repo: Optional[UserRepository] = None,
        membership_repo: Optional[UserOrgMembershipRepository] = None,
        instance_repo: Optional[OrchestratorInstanceRepository] = None,
    ):
        self.org_repo = org_repo
        self.org_settings_repo = org_settings_repo
        self.org_llm_config_repo = org_llm_config_repo
        self.user_repo = user_repo
        self.membership_repo = membership_repo
        self.instance_repo = instance_repo

    def get_user_repo(self) -> UserRepository | None:
        return self.user_repo

    def get_org_repo(self) -> OrganizationRepository:
        return self.org_repo

    def get_org_settings_repo(self) -> OrganizationSettingsRepository:
        return self.org_settings_repo

    def get_org_llm_config_repo(self) -> OrganizationLLMConfigRepository:
        return self.org_llm_config_repo

    def get_instance_repo(self) -> OrchestratorInstanceRepository | None:
        return self.instance_repo

    def get_membership_repo(self) -> UserOrgMembershipRepository | None:
        return self.membership_repo
