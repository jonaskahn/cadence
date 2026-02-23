"""LangGraph supervisor orchestrator implementation (v1.0+).

IMPORTANT: This code requires LangChain v1.0+ and is NOT backward compatible
with pre-v1.0 versions. Key v1.0+ features used:
- Annotated message reducers (add_messages)
- Model.bind_tools() with v1.0+ tool format
- StateGraph with v1.0+ API
"""

from cadence.engine.impl.langgraph.supervisor.core import LangGraphSupervisor

__all__ = ["LangGraphSupervisor"]
