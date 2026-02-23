"""Shared model pool for memory-efficient LLM instance reuse.

Models are keyed by (llm_config_id, temperature, max_tokens) and reference-counted,
so multiple orchestrator instances can share the same model object.
"""

import asyncio
import logging
from typing import Any, Dict, Tuple

from cadence.engine.shared_resources.base_cache import BaseSharedCache

logger = logging.getLogger(__name__)


class SharedModelPool(BaseSharedCache):
    """Shared pool for LLM model instances with reference counting.

    Models are keyed by (llm_config_id, temperature, max_tokens).
    Reference counting ensures models are only cleaned up when no longer used.

    Attributes:
        _registry: Dict mapping model key to (model, ref_count) tuple
        _lock: Async lock for concurrent access safety
    """

    def __init__(self):
        self._registry: Dict[Tuple, Tuple[Any, int]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _compute_key(
        llm_config_id: int,
        model_name: str,
        temperature: float,
        max_tokens: int,
    ) -> Tuple:
        return (llm_config_id, model_name, temperature, max_tokens)

    async def get_or_create(
        self,
        org_id: str,
        llm_config_id: int,
        model_name: str,
        temperature: float,
        max_tokens: int,
        factory: Any,
    ) -> Any:
        """Get existing model or create a new one via the factory.

        Args:
            org_id: Organization identifier (passed to factory for tenant isolation)
            llm_config_id: OrganizationLLMConfig primary key
            model_name: Model identifier (e.g. "gpt-4o")
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            factory: LLMModelFactory instance

        Returns:
            LLM model instance
        """
        key = self._compute_key(llm_config_id, model_name, temperature, max_tokens)

        async with self._lock:
            if key in self._registry:
                model, ref_count = self._registry[key]
                self._registry[key] = (model, ref_count + 1)
                logger.debug(
                    "Reusing model for config_id=%s model=%s, ref_count=%s",
                    llm_config_id,
                    model_name,
                    ref_count + 1,
                )
                return model

            logger.info(
                "Creating new model for config_id=%s model=%s",
                llm_config_id,
                model_name,
            )
            model = await factory.create_model_by_id(
                org_id, llm_config_id, model_name, temperature, max_tokens
            )
            self._registry[key] = (model, 1)
            return model

    async def increment_ref(
        self, llm_config_id: int, model_name: str, temperature: float, max_tokens: int
    ) -> None:
        key = self._compute_key(llm_config_id, model_name, temperature, max_tokens)
        async with self._lock:
            if key in self._registry:
                model, ref_count = self._registry[key]
                self._registry[key] = (model, ref_count + 1)
                logger.debug(
                    "Incremented ref for config_id=%s model=%s, ref_count=%s",
                    llm_config_id,
                    model_name,
                    ref_count + 1,
                )

    async def decrement_ref(
        self, llm_config_id: int, model_name: str, temperature: float, max_tokens: int
    ) -> None:
        key = self._compute_key(llm_config_id, model_name, temperature, max_tokens)
        async with self._lock:
            if key not in self._registry:
                return
            model, ref_count = self._registry[key]
            new_count = ref_count - 1
            if new_count <= 0:
                logger.info(
                    "Removing model for config_id=%s (ref_count=0)", llm_config_id
                )
                del self._registry[key]
            else:
                self._registry[key] = (model, new_count)
                logger.debug(
                    "Decremented ref for config_id=%s, ref_count=%s",
                    llm_config_id,
                    new_count,
                )

    async def cleanup(self) -> None:
        async with self._lock:
            count = len(self._registry)
            self._registry.clear()
            logger.info("Cleaned up %s models from pool", count)

    def get_stats(self) -> Dict[str, Any]:
        total_models = len(self._registry)
        total_refs = sum(ref_count for _, ref_count in self._registry.values())
        return {
            "total_models": total_models,
            "total_references": total_refs,
            "average_refs_per_model": (
                total_refs / total_models if total_models > 0 else 0
            ),
        }
