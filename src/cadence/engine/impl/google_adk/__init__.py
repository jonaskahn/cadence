"""Google ADK orchestrator backend package.

This package provides Google ADK implementation for all three orchestration modes:
- Supervisor: Single LlmAgent with all plugin tools
- Coordinator: Parent agent with sub-agents for routing
- Handoff: Peer-to-peer agent collaboration
"""

from cadence.engine.impl.google_adk.adapter import GoogleADKAdapter
from cadence.engine.impl.google_adk.coordinator import GoogleADKCoordinator
from cadence.engine.impl.google_adk.handoff import GoogleADKHandoff
from cadence.engine.impl.google_adk.streaming import GoogleADKStreamingWrapper
from cadence.engine.impl.google_adk.supervisor import GoogleADKSupervisor

__all__ = [
    "GoogleADKAdapter",
    "GoogleADKSupervisor",
    "GoogleADKCoordinator",
    "GoogleADKHandoff",
    "GoogleADKStreamingWrapper",
]
