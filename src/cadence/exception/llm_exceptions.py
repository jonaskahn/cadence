"""LLM provider and inference exceptions."""

from typing import Optional

from cadence.exception.base import CadenceException


class LLMError(CadenceException):
    """LLM operation failed."""

    def __init__(self, message: str, provider: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if provider:
            details["provider"] = provider

        super().__init__(
            message=message,
            code=kwargs.pop("code", "LLM_ERROR"),
            status_code=500,
            details=details,
            **kwargs,
        )


class LLMAPIKeyError(LLMError):
    """LLM API key is invalid or missing."""

    def __init__(self, provider: str, **kwargs):
        super().__init__(
            message=f"Invalid or missing API key for provider: {provider}",
            code="LLM_API_KEY_ERROR",
            provider=provider,
            status_code=401,
            **kwargs,
        )


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""

    def __init__(self, provider: str, **kwargs):
        super().__init__(
            message=f"LLM rate limit exceeded for provider: {provider}",
            code="LLM_RATE_LIMIT_EXCEEDED",
            provider=provider,
            status_code=429,
            **kwargs,
        )
