"""Response handlers for suspend and synthesizer nodes."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from cadence_sdk.base.loggable import Loggable
from cadence_sdk.types import AgentState
from cadence_sdk.types.state import AgentStateFields, PluginContextFields, StateHelpers
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable

from .enums import ResponseTone
from .prompts import ConversationPrompts


class StructuredResponseHandler(Loggable):
    """Handles structured response generation for different conversation nodes."""

    def __init__(self, plugin_manager):
        """Initialize with plugin manager."""
        super().__init__()
        self.plugin_manager = plugin_manager

    def get_structured_response(self, model, request_messages: List, used_plugins: List[str]) -> Any:
        """Get structured response with plugin suggestions for any model."""
        try:
            if not used_plugins:
                return model.invoke(request_messages)

            model_binder = self.plugin_manager.get_model_binder()
            structured_model, is_structured = model_binder.get_structured_model(model, used_plugins)

            if not is_structured:
                return model.invoke(request_messages)

            structured_response = structured_model.invoke(request_messages)
            return self._extract_response_content(structured_response, model, request_messages)

        except Exception:
            return model.invoke(request_messages)

    @staticmethod
    def _extract_response_content(structured_response: Any, model, request_messages: List) -> Any:
        """Extract response content from structured response."""
        if isinstance(structured_response, dict) and "response" in structured_response:
            response_content = structured_response["response"]
            return AIMessage(content=response_content)
        else:
            return model.invoke(request_messages)

    def get_model_based_structured_synthesizer_response(
        self, request_messages: List, used_plugins: List[str], state: AgentState, model
    ) -> Any:
        """Get structured synthesizer response with additional data handling."""
        try:
            if not used_plugins:
                return model.invoke(request_messages)

            model_binder = self.plugin_manager.get_model_binder()
            structured_model, is_structured = model_binder.get_structured_model(model, used_plugins)

            if not is_structured:
                return model.invoke(request_messages)

            structured_response = structured_model.invoke(request_messages)
            return self._extract_synthesizer_response_content(structured_response, state, model, request_messages)

        except Exception:
            return model.invoke(request_messages)

    @staticmethod
    def _extract_synthesizer_response_content(
        structured_response: Any, state: AgentState, model, request_messages: List
    ) -> Any:
        """Extract synthesizer response content with additional data handling."""
        if not isinstance(structured_response, dict) or "response" not in structured_response:
            return model.invoke(request_messages)

        response_content = structured_response["response"]

        if "additional_data" in structured_response:
            additional_data = structured_response["additional_data"]
            data_sources = list(additional_data.keys()) if isinstance(additional_data, dict) else []

            plugin_context = StateHelpers.get_plugin_context(state)
            plugin_context[PluginContextFields.SYNTHESIZER_OUTPUT] = {
                "response": response_content,
                "additional_data": additional_data,
                "data_sources": data_sources,
            }

        return AIMessage(content=response_content)

    def get_prompt_based_structured_synthesizer_response(
        self, request_messages: List, used_plugins: List[str], state: AgentState, model
    ) -> Any:
        """Get prompt-based structured synthesizer response with JSON parsing and backoff retry."""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                if not used_plugins:
                    return model.invoke(request_messages)
                model_binder = self.plugin_manager.get_model_binder()
                final_response_schema = model_binder.collector.create_response_schema(used_plugins)
                enhanced_messages = self._inject_schema_to_prompt(request_messages, final_response_schema)
                response = model.invoke(enhanced_messages)
                parsed_response = self._parse_json_response(response)
                if parsed_response:
                    return self._extract_synthesizer_response_content(parsed_response, state, model, request_messages)
                else:
                    return response
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning("Failed to inject schema to prompt based synthesizer response. Retrying...")
                    continue
                else:
                    self.logger.warning("Failed to inject schema to prompt based synthesizer response. Direct invoking")
                    return model.invoke(request_messages)
        return self.get_model_based_structured_synthesizer_response(state, model, request_messages)

    def _inject_schema_to_prompt(self, request_messages: List, schema_class) -> List:
        """Inject JSON schema structure into the prompt."""
        schema_description = self._generate_schema_description(schema_class)

        schema_instruction = f"""
Please respond with a valid JSON object following this exact structure:
{schema_description}

Your response must be valid JSON and include:
- "response": Main response content in markdown format
- "additional_data": Object with plugin-specific data arrays

Example format:
{
    "response": "Your main response here",
    "additional_data": {
        "internet_browser": [
            {
            ...
            },
            {
            ...
            }
        ]
    }
}
"""
        enhanced_messages = request_messages.copy()
        schema_message = SystemMessage(content=schema_instruction)
        enhanced_messages.insert(-1, schema_message)  # Insert before last user message

        return enhanced_messages

    def _generate_schema_description(self, schema_class) -> str:
        """Generate human-readable schema description from TypedDict."""
        try:
            # Get type hints from the schema class
            hints = getattr(schema_class, "__annotations__", {})

            description_parts = []
            for field_name, field_type in hints.items():
                description_parts.append(f'  "{field_name}": {self._format_type_hint(field_type)}')

            return "{\n" + ",\n".join(description_parts) + "\n}"
        except Exception:
            return '{\n  "response": "string",\n  "additional_data": "object"\n}'

    def _format_type_hint(self, type_hint) -> str:
        """Format type hint for schema description."""
        if hasattr(type_hint, "__name__"):
            return f'"{type_hint.__name__.lower()}"'
        elif hasattr(type_hint, "__origin__"):
            return '"object"'
        else:
            return '"any"'

    def _parse_json_response(self, response) -> Dict[str, Any]:
        """Parse JSON from model response with multiple extraction strategies."""
        content = response.content if hasattr(response, "content") else str(response)

        # Strategy 1: Direct JSON parsing
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract JSON from markdown code blocks
        try:
            import re

            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except (json.JSONDecodeError, AttributeError):
            pass

        # Strategy 3: Find JSON-like structure in text
        try:
            import re

            json_match = re.search(r'\{[^{}]*"response"[^{}]*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except (json.JSONDecodeError, AttributeError):
            pass

        return None


class ResponseContextBuilder:
    """Builds response context for different conversation nodes."""

    def __init__(self, plugin_manager, settings):
        """Initialize with plugin manager and settings."""
        self.plugin_manager = plugin_manager
        self.settings = settings

    def prepare_response_context(self, state: AgentState) -> tuple[str, list[str], str]:
        """Prepare common response context for suspend and synthesizer nodes."""
        metadata = StateHelpers.safe_get_metadata(state)
        requested_tone = metadata.get("tone", "natural") or "natural"
        tone_instruction = ResponseTone.get_description(requested_tone)

        plugin_context = StateHelpers.get_plugin_context(state)
        routing_history = plugin_context.get(PluginContextFields.ROUTING_HISTORY, [])
        used_plugins = list(set(routing_history))

        plugin_suggestions = self._collect_plugin_suggestions(used_plugins)
        suggestions_text = self._format_plugin_suggestions(plugin_suggestions)

        return tone_instruction, used_plugins, suggestions_text

    def _collect_plugin_suggestions(self, used_plugins: List[str]) -> Dict[str, str]:
        """Collect response suggestions from plugins that were used during the conversation."""
        suggestions = {}

        for plugin_name in used_plugins:
            plugin_bundle = self.plugin_manager.plugin_bundles.get(plugin_name)
            if plugin_bundle and plugin_bundle.metadata.response_suggestion:
                suggestions[plugin_name] = plugin_bundle.metadata.response_suggestion

        return suggestions

    @staticmethod
    def _format_plugin_suggestions(plugin_suggestions: Dict[str, str]) -> str:
        """Format plugin suggestions for inclusion in the synthesizer prompt."""
        if not plugin_suggestions:
            return ""

        formatted_suggestions = []
        for plugin_name, suggestion in plugin_suggestions.items():
            formatted_suggestions.append(f"- **{plugin_name}**: {suggestion}")

        return "\n".join(formatted_suggestions)


class SuspendHandler:
    """Handles graceful conversation termination when hop limits are exceeded."""

    def __init__(self, plugin_manager, settings, context_builder):
        """Initialize with dependencies."""
        self.plugin_manager = plugin_manager
        self.settings = settings
        self.context_builder = context_builder
        self.structured_handler = StructuredResponseHandler(plugin_manager)

    def handle_suspend(self, state: AgentState, model) -> AgentState:
        """Handle graceful conversation termination when hop limits are exceeded."""
        current_hops = StateHelpers.safe_get_agent_hops(state)
        max_hops = self.settings.max_agent_hops

        tone_instruction, used_plugins, suggestions_text = self.context_builder.prepare_response_context(state)

        suspension_message = SystemMessage(
            content=ConversationPrompts.SUSPEND_INSTRUCTIONS.format(
                current=current_hops,
                maximum=max_hops,
                tone_instruction=tone_instruction,
                current_time=datetime.now(timezone.utc).isoformat(),
                additional_suspend_context=self.settings.additional_suspend_context,
                plugin_suggestions=suggestions_text,
            )
        )

        safe_messages = self._filter_safe_messages(state[AgentStateFields.MESSAGES])
        suspension_response = self.structured_handler.get_structured_response(
            model, [suspension_message] + safe_messages, used_plugins
        )
        return StateHelpers.create_state_update(suspension_response, current_hops, state)

    @staticmethod
    def _filter_safe_messages(messages: List) -> List:
        """Remove messages with incomplete tool call sequences to prevent validation errors."""
        if not messages:
            return []
        last_message = messages[-1]
        if isinstance(last_message, AIMessage):
            messages.pop()
            return messages
        else:
            return messages


class SynthesizerHandler(Loggable):
    """Handles synthesis of complete conversation into coherent final response."""

    def __init__(self, plugin_manager, settings, context_builder):
        """Initialize with dependencies."""
        super().__init__()
        self.plugin_manager = plugin_manager
        self.settings = settings
        self.context_builder = context_builder
        self.structured_handler = StructuredResponseHandler(plugin_manager)

    def handle_synthesize(self, state: AgentState, model) -> AgentState:
        """Synthesize complete conversation into coherent final response."""
        messages = StateHelpers.safe_get_messages(state)
        tone_instruction, used_plugins, suggestions_text = self.context_builder.prepare_response_context(state)

        synthesizer_prompt = self._create_synthesizer_prompt(tone_instruction, suggestions_text)
        request_messages = self._prepare_request_messages(synthesizer_prompt, messages)
        response = self._get_synthesize_response(request_messages, used_plugins, state, model)
        response = self._normalize_response(response)

        plugin_context = StateHelpers.get_plugin_context(state)
        updated_state = StateHelpers.update_plugin_context(state, **plugin_context)
        return StateHelpers.create_state_update(response, StateHelpers.safe_get_agent_hops(state), updated_state)

    def _create_synthesizer_prompt(self, tone_instruction: str, suggestions_text: str) -> SystemMessage:
        """Create the synthesizer prompt with context."""
        synthesizer_prompt_content = ConversationPrompts.SYNTHESIZER_INSTRUCTIONS.format(
            tone_instruction=tone_instruction,
            current_time=datetime.now(timezone.utc).isoformat(),
            additional_synthesizer_context=self.settings.additional_synthesizer_context,
            plugin_suggestions=suggestions_text,
        )
        return SystemMessage(content=synthesizer_prompt_content)

    def _prepare_request_messages(self, synthesizer_prompt: SystemMessage, messages: List[Any]) -> List[Any]:
        """Prepare request messages for synthesis."""
        if not self.settings.synthesizer_compact_messages:
            return [synthesizer_prompt] + messages

        head_messages, compacted_context_msg = self._compact_messages_for_synthesizer(messages)
        if compacted_context_msg is not None:
            return [synthesizer_prompt] + head_messages + [compacted_context_msg]
        else:
            return [synthesizer_prompt] + messages

    def _compact_messages_for_synthesizer(self, messages: List[Any]) -> tuple[List[Any], Any]:
        """Compact tool call/result chains after the last human message into one SystemMessage.

        Returns a tuple of (kept_messages_head, compacted_system_message_or_None).
        """
        if not messages:
            return [], None

        head, tail = self._split_messages_at_last_human(messages)
        if not tail:
            return head, None

        compacted_text = self._build_compacted_text(tail)
        return head, SystemMessage(content=compacted_text, name="compacted_context_msg")

    @staticmethod
    def _split_messages_at_last_human(messages: List[Any]) -> tuple[List[Any], List[Any]]:
        """Split messages at the last human message."""
        last_human_idx = -1
        for idx, msg in enumerate(messages):
            if isinstance(msg, HumanMessage) or getattr(msg, "type", None) == "human":
                last_human_idx = idx

        head = messages if last_human_idx < 0 else messages[: last_human_idx + 1]
        tail = [] if last_human_idx < 0 else messages[last_human_idx + 1 :]
        return head, tail

    def _build_compacted_text(self, tail_messages: List[Any]) -> str:
        """Build compacted text from tail messages."""
        header = self.settings.synthesizer_compaction_header
        max_chars = self.settings.synthesizer_compaction_max_chars

        lines: List[str] = [header]
        for msg in tail_messages:
            self._process_message_for_compaction(msg, lines)

        compacted_text = "\n".join(lines)
        if len(compacted_text) > max_chars:
            compacted_text = compacted_text[: max_chars - 100] + "\n... (truncated)"
        return compacted_text

    def _process_message_for_compaction(self, msg: Any, lines: List[str]) -> None:
        """Process a single message for compaction."""
        try:
            if isinstance(msg, AIMessage):
                self._process_ai_message(msg, lines)
            elif isinstance(msg, ToolMessage):
                self._process_tool_message(msg, lines)
            else:
                self._process_other_message(msg, lines)
        except Exception:
            pass

    @staticmethod
    def _process_ai_message(msg: AIMessage, lines: List[str]) -> None:
        """Process AI message for compaction."""
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for call in tool_calls:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "tool")
                if name == "goto_synthesize":
                    continue
                args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
                lines.append(f"- AI tool call: {name} args: {str(args)[:500]}")

        content = getattr(msg, "content", None)
        if content and not tool_calls:
            text = content if isinstance(content, str) else str(content)
            if text:
                lines.append(f"- AI: {text[:500]}")

    @staticmethod
    def _process_tool_message(msg: ToolMessage, lines: List[str]) -> None:
        """Process tool message for compaction."""
        tool_name = getattr(msg, "name", None) or getattr(msg, "tool", None) or "tool"
        if tool_name == "goto_synthesize":
            return

        content = getattr(msg, "content", "")
        text = content if isinstance(content, str) else str(content)
        lines.append(f"- Tool result ({tool_name}): {text[:1000]}")

    @staticmethod
    def _process_other_message(msg: Any, lines: List[str]) -> None:
        """Process other message types for compaction."""
        content = getattr(msg, "content", None)
        if content:
            text = content if isinstance(content, str) else str(content)
            lines.append(f"- Note: {text[:500]}")

    def _get_synthesize_response(
        self, request_messages: List[Any], used_plugins: List[str], state: AgentState, model
    ) -> Any:
        """Get the final response using structured synthesizer modes: model, prompt, or none."""
        synthesizer_mode = self.settings.use_structured_synthesizer

        if not synthesizer_mode or not used_plugins:
            return model.invoke(request_messages)

        if synthesizer_mode == "model":
            self.logger.info("Using model structured synthesizer mode")
            return self.structured_handler.get_model_based_structured_synthesizer_response(
                request_messages, used_plugins, state, model
            )
        elif synthesizer_mode == "prompt":
            self.logger.info("Using prompt structured synthesizer mode")
            return self.structured_handler.get_prompt_based_structured_synthesizer_response(
                request_messages, used_plugins, state, model
            )
        else:
            return model.invoke(request_messages)

    def _normalize_response(self, final_response: Any) -> AIMessage:
        """Normalize the final response to AIMessage format."""
        if self.settings.synthesizer_compact_messages and not isinstance(final_response, AIMessage):
            if hasattr(final_response, "content"):
                return AIMessage(content=final_response.content)
            else:
                return AIMessage(content=str(final_response))
        return final_response


class TimeoutHandler:
    """Handles timeout mechanism for coordinator invoke when not allowed to terminate."""

    def __init__(self, settings):
        """Initialize timeout handler with settings."""
        self.settings = settings

    async def invoke_with_timeout(self, coordinator_model, request_messages: List) -> AIMessage:
        """
        Invoke coordinator model with timeout mechanism.

        If coordinator exceeds timeout and is not allowed to terminate,
        creates a suspend fallback response with fake ToolCall.

        Args:
            coordinator_model: The coordinator model to invoke
            request_messages: List of messages for the coordinator

        Returns:
            AIMessage: Response from coordinator or suspend fallback
        """
        if self.settings.allowed_coordinator_terminate:
            return coordinator_model.invoke(request_messages)

        try:
            runnable = Runnable.from_function(coordinator_model.invoke)
            response = await asyncio.wait_for(
                runnable.ainvoke(request_messages), timeout=self.settings.coordinator_invoke_timeout
            )
            return response
        except asyncio.TimeoutError:
            return self._create_suspend_fallback_response()

    def _create_suspend_fallback_response(self) -> AIMessage:
        """
        Create a suspend fallback response when coordinator times out.

        Returns:
            AIMessage: Fake response with goto_synthesize tool call
        """
        from langchain_core.messages import ToolCall

        return AIMessage(content="", tool_calls=[ToolCall(id=str(uuid.uuid4()), name="goto_synthesize", args={})])
