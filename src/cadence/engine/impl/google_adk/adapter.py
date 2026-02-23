"""Google ADK adapter — not yet implemented."""

from typing import Any, Dict, List

from cadence_sdk.types.sdk_messages import UvMessage
from cadence_sdk.types.sdk_state import UvState
from cadence_sdk.types.sdk_tools import UvTool

from cadence.engine.base import OrchestratorAdapter


class GoogleADKAdapter(OrchestratorAdapter):
    """Placeholder adapter for Google ADK. Not yet implemented."""

    def __init__(self):
        super().__init__(framework_type="google_adk")

    def sdk_message_to_orchestrator(self, sdk_msg: UvMessage) -> dict:
        raise NotImplementedError("Google ADK backend is not yet implemented")

    def orchestrator_message_to_sdk(self, orch_msg: dict) -> UvMessage:
        raise NotImplementedError("Google ADK backend is not yet implemented")

    def uvtool_to_orchestrator(self, uvtool: UvTool) -> Any:
        raise NotImplementedError("Google ADK backend is not yet implemented")

    def bind_tools_to_model(self, model: Any, tools: List[UvTool], **kwargs) -> Any:
        raise NotImplementedError("Google ADK backend is not yet implemented")

    def create_tool_node(self, tools: List[UvTool]) -> Any:
        raise NotImplementedError("Google ADK backend is not yet implemented")

    def sync_state_to_session(self, state: UvState) -> Dict[str, Any]:
        raise NotImplementedError("Google ADK backend is not yet implemented")

    def sync_session_to_state(
        self, session_state: Dict[str, Any], state: UvState
    ) -> UvState:
        raise NotImplementedError("Google ADK backend is not yet implemented")
