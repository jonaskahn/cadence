"""Response handlers for suspend and synthesizer nodes."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from cadence_sdk.types import AgentState
from cadence_sdk.types.state import AgentStateFields, PluginContextFields, StateHelpers
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from .enums import ResponseTone
from .prompts import ConversationPrompts


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
        tone_instruction = self._get_tone_instruction(requested_tone)

        plugin_context = StateHelpers.get_plugin_context(state)
        routing_history = plugin_context.get(PluginContextFields.ROUTING_HISTORY, [])
        used_plugins = list(set(routing_history))

        plugin_suggestions = self._collect_plugin_suggestions(used_plugins)
        suggestions_text = self._format_plugin_suggestions(plugin_suggestions)

        return tone_instruction, used_plugins, suggestions_text

    def _get_tone_instruction(self, tone: str) -> str:
        """Return appropriate tone instruction based on requested response style."""
        return ResponseTone.get_description(tone)

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

    def handle_suspend(self, state: AgentState, model) -> AgentState:
        """Handle graceful conversation termination when hop limits are exceeded."""
        current_hops = StateHelpers.safe_get_agent_hops(state)
        max_hops = self.settings.max_agent_hops

        tone_instruction, used_plugins, suggestions_text = self.context_builder.prepare_response_context(state)

        suspension_message = SystemMessage(
            content=ConversationPrompts.HOP_LIMIT_REACHED.format(
                current=current_hops,
                maximum=max_hops,
                tone_instruction=tone_instruction,
                current_time=datetime.now(timezone.utc).isoformat(),
                additional_suspend_context=self.settings.additional_suspend_context,
                plugin_suggestions=suggestions_text,
            )
        )

        safe_messages = self._filter_safe_messages(state[AgentStateFields.MESSAGES])
        suspension_response = self._get_structured_response(model, [suspension_message] + safe_messages, used_plugins)
        return StateHelpers.create_state_update(suspension_response, current_hops, state)

    def _get_structured_response(self, model, request_messages: List, used_plugins: List[str]) -> Any:
        """Get structured response with plugin suggestions for any model."""
        try:
            if used_plugins:
                model_binder = self.plugin_manager.get_model_binder()
                structured_model, is_structured = model_binder.get_structured_model(model, used_plugins)

                if is_structured:
                    structured_response = structured_model.invoke(request_messages)

                    if isinstance(structured_response, dict) and "response" in structured_response:
                        response_content = structured_response["response"]
                        return AIMessage(content=response_content)
                    else:
                        return model.invoke(request_messages)
                else:
                    return model.invoke(request_messages)
            else:
                return model.invoke(request_messages)

        except Exception as e:
            return model.invoke(request_messages)

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


class SynthesizerHandler:
    """Handles synthesis of complete conversation into coherent final response."""

    def __init__(self, plugin_manager, settings, context_builder):
        """Initialize with dependencies."""
        self.plugin_manager = plugin_manager
        self.settings = settings
        self.context_builder = context_builder

    def handle_synthesize(self, state: AgentState, model) -> AgentState:
        """Synthesize complete conversation into coherent final response."""
        messages = StateHelpers.safe_get_messages(state)

        tone_instruction, used_plugins, suggestions_text = self.context_builder.prepare_response_context(state)

        synthesizer_prompt_content = ConversationPrompts.SYNTHESIZER_INSTRUCTIONS.format(
            tone_instruction=tone_instruction,
            current_time=datetime.now(timezone.utc).isoformat(),
            additional_synthesizer_context=self.settings.additional_synthesizer_context,
            plugin_suggestions=suggestions_text,
        )
        synthesizer_prompt = SystemMessage(content=synthesizer_prompt_content)

        request_messages: List[Any]
        if getattr(self.settings, "synthesizer_compact_messages", False):
            head_messages, compacted_context_msg = self._compact_messages_for_synthesizer(messages)
            if compacted_context_msg is not None:
                request_messages = [synthesizer_prompt] + head_messages + [compacted_context_msg]
            else:
                request_messages = [synthesizer_prompt] + messages
        else:
            request_messages = [synthesizer_prompt] + messages

        if self.settings.enable_structured_synthesizer and used_plugins:
            final_response = self._get_structured_synthesizer_response(request_messages, used_plugins, state, model)
        else:
            final_response = model.invoke(request_messages)

        # In compact mode, ensure we return a proper AI message to maintain graph flow
        if getattr(self.settings, "synthesizer_compact_messages", False) and not isinstance(final_response, AIMessage):
            if hasattr(final_response, "content"):
                final_response = AIMessage(content=final_response.content)
            else:
                final_response = AIMessage(content=str(final_response))

        plugin_context = StateHelpers.get_plugin_context(state)
        updated_state = StateHelpers.update_plugin_context(state, **plugin_context)
        return StateHelpers.create_state_update(final_response, StateHelpers.safe_get_agent_hops(state), updated_state)

    def _compact_messages_for_synthesizer(self, messages: List[Any]) -> tuple[List[Any], Any]:
        """Compact tool call/result chains after the last human message into one SystemMessage.

        Returns a tuple of (kept_messages_head, compacted_system_message_or_None).
        """
        if not messages:
            return [], None

        # Find index of the last HumanMessage
        last_human_idx = -1
        for idx, msg in enumerate(messages):
            if isinstance(msg, HumanMessage) or getattr(msg, "type", None) == "human":
                last_human_idx = idx

        # Keep everything up to and including the last human message
        head = messages if last_human_idx < 0 else messages[: last_human_idx + 1]
        tail = [] if last_human_idx < 0 else messages[last_human_idx + 1 :]

        if not tail:
            return head, None

        header = getattr(
            self.settings, "synthesizer_compaction_header", "Context from tools and intermediate steps (compacted):"
        )
        max_chars = int(getattr(self.settings, "synthesizer_compaction_max_chars", 6000) or 6000)

        lines: List[str] = [header]
        for msg in tail:
            try:
                if isinstance(msg, AIMessage):
                    tool_calls = getattr(msg, "tool_calls", None)
                    if tool_calls:
                        for call in tool_calls:
                            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "tool")
                            # Skip goto_synthesize tool calls
                            if name == "goto_synthesize":
                                continue
                            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
                            lines.append(f"- AI tool call: {name} args: {str(args)[:500]}")
                    content = getattr(msg, "content", None)
                    if content and not tool_calls:
                        text = content if isinstance(content, str) else str(content)
                        if text:
                            lines.append(f"- AI: {text[:500]}")
                elif isinstance(msg, ToolMessage):
                    tool_name = getattr(msg, "name", None) or getattr(msg, "tool", None) or "tool"
                    # Skip goto_synthesize tool results
                    if tool_name == "goto_synthesize":
                        continue
                    content = getattr(msg, "content", "")
                    text = content if isinstance(content, str) else str(content)
                    lines.append(f"- Tool result ({tool_name}): {text[:1000]}")
                else:
                    # Other message types: include brief content if available
                    content = getattr(msg, "content", None)
                    if content:
                        text = content if isinstance(content, str) else str(content)
                        lines.append(f"- Note: {text[:500]}")
            except Exception:
                continue

        compacted_text = "\n".join(lines)
        if len(compacted_text) > max_chars:
            compacted_text = compacted_text[: max_chars - 100] + "\n... (truncated)"

        return head, SystemMessage(content=compacted_text, name="compacted_context_msg")

    def _get_structured_synthesizer_response(
        self, request_messages: List, used_plugins: List[str], state: AgentState, model
    ) -> Any:
        """Get structured synthesizer response with additional data handling."""
        try:
            model_binder = self.plugin_manager.get_model_binder()
            structured_model, is_structured = model_binder.get_structured_model(model, used_plugins)

            if is_structured:
                structured_response = structured_model.invoke(request_messages)

                if isinstance(structured_response, dict) and "response" in structured_response:
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
                else:
                    return model.invoke(request_messages)
            else:
                return model.invoke(request_messages)

        except Exception as e:
            return model.invoke(request_messages)
