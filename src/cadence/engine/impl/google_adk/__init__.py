"""Google ADK orchestrator backend package.

This package provides Google ADK implementation for all orchestration modes:
- Supervisor: Single LlmAgent with all plugin tools
- Coordinator: Parent agent with sub-agents for routing
- Handoff: Peer-to-peer agent collaboration
- Pipeline: Fixed sequential stage execution (placeholder)
- Reflection: Generator-critic iterative loop (placeholder)
- Ensemble: Parallel multi-agent synthesis (placeholder)
- Hierarchical: Two-level supervisor hierarchy (placeholder)
"""

from cadence.engine.impl.google_adk.adapter import GoogleADKAdapter
from cadence.engine.impl.google_adk.coordinator import GoogleADKCoordinator
from cadence.engine.impl.google_adk.ensemble import GoogleADKEnsemble
from cadence.engine.impl.google_adk.handoff import GoogleADKHandoff
from cadence.engine.impl.google_adk.hierarchical import GoogleADKHierarchical
from cadence.engine.impl.google_adk.pipeline import GoogleADKPipeline
from cadence.engine.impl.google_adk.reflection import GoogleADKReflection
from cadence.engine.impl.google_adk.streaming import GoogleADKStreamingWrapper
from cadence.engine.impl.google_adk.supervisor import GoogleADKSupervisor

__all__ = [
    "GoogleADKAdapter",
    "GoogleADKCoordinator",
    "GoogleADKEnsemble",
    "GoogleADKHandoff",
    "GoogleADKHierarchical",
    "GoogleADKPipeline",
    "GoogleADKReflection",
    "GoogleADKStreamingWrapper",
    "GoogleADKSupervisor",
]
