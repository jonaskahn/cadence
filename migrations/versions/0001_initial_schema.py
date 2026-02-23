"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-02-26

"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from cadence.infrastructure.persistence.postgresql.models import BaseModel

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEED: list[tuple[str, str, str, list[str]]] = [
    # ── OpenAI Chat ──────────────────────────────────────────────────────────
    ("openai", "gpt-4o", "GPT-4o", ["4o"]),
    ("openai", "chatgpt-4o-latest", "ChatGPT-4o Latest", ["chatgpt-4o"]),
    ("openai", "gpt-4o-mini", "GPT-4o Mini", ["4o-mini"]),
    ("openai", "gpt-4o-audio-preview", "GPT-4o Audio Preview", []),
    (
        "openai",
        "gpt-4o-audio-preview-2024-12-17",
        "GPT-4o Audio Preview (2024-12-17)",
        [],
    ),
    (
        "openai",
        "gpt-4o-audio-preview-2024-10-01",
        "GPT-4o Audio Preview (2024-10-01)",
        [],
    ),
    ("openai", "gpt-4o-mini-audio-preview", "GPT-4o Mini Audio Preview", []),
    (
        "openai",
        "gpt-4o-mini-audio-preview-2024-12-17",
        "GPT-4o Mini Audio Preview (2024-12-17)",
        [],
    ),
    ("openai", "gpt-4.1", "GPT-4.1", ["4.1"]),
    ("openai", "gpt-4.1-mini", "GPT-4.1 Mini", ["4.1-mini"]),
    ("openai", "gpt-4.1-nano", "GPT-4.1 Nano", ["4.1-nano"]),
    ("openai", "gpt-3.5-turbo", "GPT-3.5 Turbo", ["3.5", "chatgpt"]),
    ("openai", "gpt-3.5-turbo-16k", "GPT-3.5 Turbo 16K", ["chatgpt-16k", "3.5-16k"]),
    ("openai", "gpt-4", "GPT-4", ["4", "gpt4"]),
    ("openai", "gpt-4-32k", "GPT-4 32K", ["4-32k"]),
    ("openai", "gpt-4-1106-preview", "GPT-4 Turbo (1106 Preview)", []),
    ("openai", "gpt-4-0125-preview", "GPT-4 Turbo (0125 Preview)", []),
    ("openai", "gpt-4-turbo-2024-04-09", "GPT-4 Turbo (2024-04-09)", []),
    ("openai", "gpt-4-turbo", "GPT-4 Turbo", ["gpt-4-turbo-preview", "4-turbo", "4t"]),
    ("openai", "gpt-4.5-preview-2025-02-27", "GPT-4.5 Preview (2025-02-27)", []),
    ("openai", "gpt-4.5-preview", "GPT-4.5 Preview", ["gpt-4.5"]),
    ("openai", "o1", "o1", []),
    ("openai", "o1-2024-12-17", "o1 (2024-12-17)", []),
    ("openai", "o1-preview", "o1 Preview", []),
    ("openai", "o1-mini", "o1 Mini", []),
    ("openai", "o3-mini", "o3 Mini", []),
    ("openai", "o3", "o3", []),
    ("openai", "o4-mini", "o4 Mini", []),
    ("openai", "gpt-5", "GPT-5", []),
    ("openai", "gpt-5-mini", "GPT-5 Mini", []),
    ("openai", "gpt-5-nano", "GPT-5 Nano", []),
    ("openai", "gpt-5-2025-08-07", "GPT-5 (2025-08-07)", []),
    ("openai", "gpt-5-mini-2025-08-07", "GPT-5 Mini (2025-08-07)", []),
    ("openai", "gpt-5-nano-2025-08-07", "GPT-5 Nano (2025-08-07)", []),
    ("openai", "gpt-5.1", "GPT-5.1", []),
    ("openai", "gpt-5.1-chat-latest", "GPT-5.1 Chat Latest", []),
    ("openai", "gpt-5.2", "GPT-5.2", []),
    ("openai", "gpt-5.2-chat-latest", "GPT-5.2 Chat Latest", []),
    # ── OpenAI Completion ────────────────────────────────────────────────────
    (
        "openai",
        "gpt-3.5-turbo-instruct",
        "GPT-3.5 Turbo Instruct",
        ["3.5-instruct", "chatgpt-instruct"],
    ),
    # ── Anthropic ────────────────────────────────────────────────────────────
    ("anthropic", "claude-opus-4-6", "Claude Opus 4.6", []),
    ("anthropic", "claude-sonnet-4-6", "Claude Sonnet 4.6", []),
    ("anthropic", "claude-haiku-4-5-20251001", "Claude Haiku 4.5", []),
    (
        "anthropic",
        "claude-3-5-sonnet-20241022",
        "Claude 3.5 Sonnet",
        ["claude-3-5-sonnet"],
    ),
    (
        "anthropic",
        "claude-3-5-haiku-20241022",
        "Claude 3.5 Haiku",
        ["claude-3-5-haiku"],
    ),
    ("anthropic", "claude-3-opus-20240229", "Claude 3 Opus", ["claude-3-opus"]),
    ("anthropic", "claude-3-sonnet-20240229", "Claude 3 Sonnet", ["claude-3-sonnet"]),
    ("anthropic", "claude-3-haiku-20240307", "Claude 3 Haiku", ["claude-3-haiku"]),
    # ── Google ───────────────────────────────────────────────────────────────
    ("google", "gemini-2.0-flash", "Gemini 2.0 Flash", []),
    ("google", "gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", []),
    ("google", "gemini-1.5-pro", "Gemini 1.5 Pro", []),
    ("google", "gemini-1.5-flash", "Gemini 1.5 Flash", []),
    ("google", "gemini-1.5-flash-8b", "Gemini 1.5 Flash 8B", []),
    # ── Groq ─────────────────────────────────────────────────────────────────
    ("groq", "llama-3.3-70b-versatile", "Llama 3.3 70B Versatile", []),
    ("groq", "llama-3.1-8b-instant", "Llama 3.1 8B Instant", []),
    ("groq", "llama3-70b-8192", "Llama3 70B", []),
    ("groq", "llama3-8b-8192", "Llama3 8B", []),
    ("groq", "mixtral-8x7b-32768", "Mixtral 8x7B", []),
    ("groq", "gemma2-9b-it", "Gemma2 9B IT", []),
]


def upgrade() -> None:
    bind = op.get_bind()
    BaseModel.metadata.drop_all(bind=bind)
    BaseModel.metadata.create_all(bind=bind)

    bind.execute(
        sa.text(
            "INSERT INTO provider_model_configs "
            "(provider, model_id, display_name, aliases, is_active, created_at, updated_at) "
            "VALUES (:provider, :model_id, :display_name, CAST(:aliases AS jsonb), true, NOW(), NOW())"
        ),
        [
            {
                "provider": provider,
                "model_id": model_id,
                "display_name": display_name,
                "aliases": json.dumps(aliases),
            }
            for provider, model_id, display_name, aliases in _SEED
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    BaseModel.metadata.drop_all(bind=bind)
