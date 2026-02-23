"""LLM configuration and provider model API endpoints."""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from cadence.constants.framework import (
    FRAMEWORK_SUPPORTED_MODES,
    FRAMEWORK_SUPPORTED_PROVIDERS,
    Framework,
)
from cadence.controller.schemas.tenant_schemas import (
    AddLLMConfigRequest,
    FrameworkSupportedProvidersResponse,
    LLMConfigResponse,
    ProviderModelResponse,
    UpdateLLMConfigRequest,
)
from cadence.middleware.authorization_middleware import (
    require_authenticated,
    require_org_admin_access,
)
from cadence.middleware.tenant_context_middleware import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tenants"])

_FOREIGN_KEY_ERROR_MARKERS = ("foreign key", "fk")


def _build_llm_response(config: Any) -> LLMConfigResponse:
    """Build LLMConfigResponse from ORM object, masking the API key."""
    return LLMConfigResponse(
        id=str(config.id),
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        additional_config=config.additional_config,
        created_at=config.created_at.isoformat(),
    )


@router.post(
    "/api/orgs/{org_id}/llm-configs",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_llm_config(
    org_id: str,
    config_request: AddLLMConfigRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Add LLM configuration (BYOK). Accessible by org_admin only."""
    tenant_service = request.app.state.tenant_service
    try:
        config = await tenant_service.add_llm_config(
            org_id=org_id,
            name=config_request.name,
            provider=config_request.provider,
            api_key=config_request.api_key,
            base_url=config_request.base_url,
            additional_config=config_request.additional_config,
            caller_id=context.user_id,
        )
        return _build_llm_response(config)
    except IntegrityError as e:
        err = str(e).lower()
        if any(marker in err for marker in _FOREIGN_KEY_ERROR_MARKERS):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="LLM config already exists"
        )
    except Exception as e:
        logger.error(f"Failed to add LLM config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add LLM configuration",
        )


@router.get(
    "/api/orgs/{org_id}/llm-configs",
    response_model=List[LLMConfigResponse],
    dependencies=[Depends(require_org_admin_access)],
)
async def list_llm_configs(
    org_id: str,
    request: Request,
):
    """List LLM configurations (API key masked)."""
    tenant_service = request.app.state.tenant_service
    try:
        configs = await tenant_service.list_llm_configs(org_id)
        return [_build_llm_response(c) for c in configs]
    except Exception as e:
        logger.error(f"Failed to list LLM configs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list LLM configurations",
        )


@router.get(
    "/api/providers/{provider}/models",
    response_model=List[ProviderModelResponse],
    dependencies=[Depends(require_authenticated)],
)
async def list_provider_models(provider: str, request: Request):
    """List known models for a given LLM provider."""
    provider_model_repo = request.app.state.provider_model_repo
    try:
        models = await provider_model_repo.get_by_provider(provider)
        return [
            ProviderModelResponse(
                model_id=m.model_id,
                display_name=m.display_name,
                aliases=m.aliases or [],
            )
            for m in models
        ]
    except Exception as e:
        logger.error(
            f"Failed to list models for provider {provider}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list provider models",
        )


@router.get(
    "/api/frameworks",
    response_model=List[FrameworkSupportedProvidersResponse],
    dependencies=[Depends(require_authenticated)],
)
async def list_frameworks():
    """Return all supported frameworks with their capabilities."""
    result = []
    for fw in Framework:
        providers = FRAMEWORK_SUPPORTED_PROVIDERS.get(fw)
        modes = FRAMEWORK_SUPPORTED_MODES.get(fw, frozenset())
        result.append(
            FrameworkSupportedProvidersResponse(
                framework_type=fw.value,
                supported_providers=sorted(providers) if providers else None,
                supports_all=providers is None,
                supported_modes=sorted(modes),
            )
        )
    return result


@router.get(
    "/api/frameworks/{framework_type}/supported-providers",
    response_model=FrameworkSupportedProvidersResponse,
    dependencies=[Depends(require_authenticated)],
)
async def get_framework_supported_providers(framework_type: str):
    """Return provider names supported by the given orchestration framework."""
    try:
        fw = Framework(framework_type)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Unknown framework: {framework_type}"
        )

    providers = FRAMEWORK_SUPPORTED_PROVIDERS.get(fw)
    modes = FRAMEWORK_SUPPORTED_MODES.get(fw, frozenset())
    return FrameworkSupportedProvidersResponse(
        framework_type=framework_type,
        supported_providers=sorted(providers) if providers else None,
        supports_all=providers is None,
        supported_modes=sorted(modes),
    )


@router.patch(
    "/api/orgs/{org_id}/llm-configs/{config_name}",
    response_model=LLMConfigResponse,
)
async def update_llm_config(
    org_id: str,
    config_name: str,
    update_request: UpdateLLMConfigRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Update an LLM configuration (provider is immutable)."""
    tenant_service = request.app.state.tenant_service
    try:
        updates = update_request.model_dump(exclude_unset=True)
        # Empty api_key string means "keep existing"
        if "api_key" in updates and not updates["api_key"]:
            del updates["api_key"]

        config = await tenant_service.update_llm_config(
            org_id=org_id,
            name=config_name,
            updates=updates,
            caller_id=context.user_id,
        )
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM config '{config_name}' not found",
            )
        return _build_llm_response(config)
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Config name already exists",
        )
    except Exception as e:
        logger.error(f"Failed to update LLM config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update LLM configuration",
        )


@router.delete(
    "/api/orgs/{org_id}/llm-configs/{config_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_llm_config(
    org_id: str,
    config_name: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Soft-delete an LLM configuration."""
    tenant_service = request.app.state.tenant_service
    try:
        deleted = await tenant_service.delete_llm_config(
            org_id=org_id,
            name=config_name,
            caller_id=context.user_id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM config '{config_name}' not found",
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete LLM config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete LLM configuration",
        )
