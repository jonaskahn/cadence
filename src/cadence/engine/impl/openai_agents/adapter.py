"""OpenAI Agents SDK adapter — not yet implemented."""

from typing import Any, List

from cadence_sdk.types.sdk_messages import UvMessage
from cadence_sdk.types.sdk_tools import UvTool

from cadence.engine.base import OrchestratorAdapter


class OpenAIAgentsAdapter(OrchestratorAdapter):
    """Placeholder adapter for OpenAI Agents SDK. Not yet implemented."""

    def __init__(self):
        super().__init__(framework_type="openai_agents")

    def sdk_message_to_orchestrator(self, sdk_msg: UvMessage) -> dict:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")

    def orchestrator_message_to_sdk(self, orch_msg: dict) -> UvMessage:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")

    def uvtool_to_orchestrator(self, uvtool: UvTool) -> dict:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")

    def bind_tools_to_model(self, model: Any, tools: List[UvTool], **kwargs) -> list:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")

    def create_tool_node(self, tools: List[UvTool]) -> None:
        raise NotImplementedError("OpenAI Agents SDK backend is not yet implemented")
