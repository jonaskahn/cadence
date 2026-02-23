"""Cadence v2 - Multi-tenant, multi-orchestrator AI agent platform.

Cadence provides a complete framework for building and deploying AI agents
with support for multiple orchestration backends (LangGraph, OpenAI Agents,
Google ADK) and multiple orchestration modes (supervisor, coordinator, handoff).

Key Features:
- Multi-tenant architecture with per-organization isolation
- 3-tier runtime settings cascade (Global → Organization → Instance) with RabbitMQ broadcast
- BYOK (Bring Your Own Key) for LLM providers
- Hot-reload configuration without restart
- Database-per-organization for MongoDB (conversation storage)
- Infrastructure config via .env (immutable); operational defaults in global_settings DB table
- LRU-based orchestrator pool with Hot/Warm/Cold tiers

Architecture:
- cadence-sdk: Framework-agnostic plugin development kit
- cadence: Runtime framework with orchestration engines

Version: 2.0.0
"""

__version__ = "2.0.0"
