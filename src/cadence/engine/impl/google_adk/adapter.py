"""Google ADK adapter — bidirectional conversion between SDK and ADK types."""

from typing import Any, Optional

from cadence_sdk.types.sdk_messages import (
    UvAIMessage,
    UvHumanMessage,
    UvMessage,
    UvSystemMessage,
    UvToolMessage,
)
from cadence_sdk.types.sdk_tools import UvTool
from google.adk.events import Event
from google.adk.tools import FunctionTool
from google.genai.types import Content, Part

from cadence.engine.base import OrchestratorAdapter


class GoogleADKAdapter(OrchestratorAdapter):
    """Adapter for Google ADK orchestration backend.

    Converts between Cadence SDK types (UvMessage, UvTool) and Google ADK
    native types (Content, FunctionTool).
    """

    def __init__(self):
        super().__init__(framework_type="google_adk")

    def sdk_message_to_orchestrator(self, sdk_msg: UvMessage) -> Optional[Content]:
        """Convert SDK message to ADK Content.

        UvSystemMessage is handled separately (used as LlmAgent instruction).
        Returns None for system messages so callers can skip them.
        """
        if isinstance(sdk_msg, UvHumanMessage) or (
            hasattr(sdk_msg, "role") and sdk_msg.role == "human"
        ):
            return Content(role="user", parts=[Part(text=sdk_msg.content or "")])

        if isinstance(sdk_msg, UvAIMessage) or (
            hasattr(sdk_msg, "role") and sdk_msg.role == "ai"
        ):
            return Content(role="model", parts=[Part(text=sdk_msg.content or "")])

        if isinstance(sdk_msg, UvSystemMessage) or (
            hasattr(sdk_msg, "role") and sdk_msg.role == "system"
        ):
            return None

        if isinstance(sdk_msg, UvToolMessage) or (
            hasattr(sdk_msg, "role") and sdk_msg.role == "tool"
        ):
            return Content(role="user", parts=[Part(text=sdk_msg.content or "")])

        return None

    def sdk_message_to_event(self, sdk_msg: UvMessage) -> Optional[Event]:
        """Convert SDK message to ADK Event for session history injection."""
        content = self.sdk_message_to_orchestrator(sdk_msg)
        if content is None:
            return None
        author = "user" if content.role == "user" else "model"
        return Event(author=author, content=content)

    def orchestrator_message_to_sdk(self, orch_msg: Any) -> UvMessage:
        """Convert ADK Content to SDK message."""
        if isinstance(orch_msg, Content):
            text = ""
            if orch_msg.parts:
                text = "".join(
                    p.text or "" for p in orch_msg.parts if hasattr(p, "text")
                )
            if orch_msg.role == "user":
                return UvHumanMessage(content=text)
            return UvAIMessage(content=text)

        raise ValueError(f"Unknown ADK message type: {type(orch_msg)}")

    def uvtool_to_orchestrator(self, uvtool: UvTool) -> FunctionTool:
        """Convert UvTool to ADK FunctionTool."""
        func = uvtool.func
        builtins_doc = func.__doc__ if hasattr(func, "__doc__") and func.__doc__ else ""
        args_schema = (
            uvtool.args_schema.model_json_schema()
            if hasattr(uvtool, "args_schema") and uvtool.args_schema
            else ""
        )
        func.__doc__ = f"{builtins_doc}\n{args_schema}".strip()
        return FunctionTool(func=uvtool.func)
