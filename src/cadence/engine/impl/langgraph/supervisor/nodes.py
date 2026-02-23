"""Node implementations for the LangGraph supervisor.

Module-level async functions receive explicit dependencies via functools.partial.
No inheritance, no abstract properties — directly testable.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel

from cadence.engine.impl.langgraph.state import MessageState
from cadence.engine.impl.langgraph.supervisor.graph_node import GraphNode
from cadence.engine.impl.langgraph.supervisor.helpers import (
    build_clarification_context,
    build_clarifier_messages,
    build_error_state,
    extract_last_human_query,
    sanitize_messages,
)
from cadence.engine.impl.langgraph.supervisor.prompts import SupervisorPrompts
from cadence.engine.utils.message_utils import count_tokens_estimate
from cadence.engine.utils.plugin_utils import (
    build_all_plugins_description,
    build_tool_descriptions,
)

logger = logging.getLogger(__name__)


class RoutingDecision(BaseModel):
    """Structured output from the router node."""

    route: Literal["tools", "conversational", "clarify"]


async def run_router_node(
    state: MessageState,
    *,
    model: Any,
    settings: Any,
    plugin_bundles: Any,
) -> Dict[str, Any]:
    """Classify user intent and store routing_decision in state."""
    try:
        messages = state.get("messages", [])

        max_context_window = getattr(settings, "max_context_window", 0)
        if max_context_window and max_context_window > 0:
            token_count = count_tokens_estimate(messages)
            if token_count > max_context_window:
                return build_error_state(
                    state,
                    RuntimeError(
                        f"Context window exceeded: {token_count} tokens > {max_context_window} limit."
                    ),
                    GraphNode.ROUTER.value,
                )

        context_window = settings.message_context_window
        recent_messages = messages[-context_window:] if context_window > 0 else messages

        plugin_desc = build_all_plugins_description(plugin_bundles)
        template = settings.classifier_node.prompt or SupervisorPrompts.ROUTER
        system_prompt = template.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            plugin_descriptions=plugin_desc,
        )

        timeout = settings.classifier_node.timeout or settings.node_execution_timeout
        try:
            result = await asyncio.wait_for(
                model.ainvoke(
                    [SystemMessage(content=system_prompt)] + list(recent_messages)
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Router timed out after %ds", timeout)
            result = None

        routing = result.route if isinstance(result, RoutingDecision) else "tools"

        return {
            "routing_decision": routing,
            "current_agent": GraphNode.ROUTER.value,
            "error_state": None,
        }

    except Exception as e:
        logger.error("Error in router node: %s", e, exc_info=True)
        return build_error_state(state, e, GraphNode.ROUTER.value)


async def run_planner_node(
    state: MessageState,
    *,
    model: Any,
    settings: Any,
    plugin_bundles: Any,
) -> Dict[str, Any]:
    """Select which tools to call to fulfil the user query."""
    try:
        messages = state.get("messages", [])
        agent_hops = state.get("agent_hops", 0)
        plugin_desc = build_all_plugins_description(plugin_bundles)
        tool_desc = build_tool_descriptions(plugin_bundles)

        template = settings.planner_node.prompt or SupervisorPrompts.PLANNER
        system_prompt = template.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            plugin_descriptions=plugin_desc,
            tool_descriptions=tool_desc,
        )

        timeout = settings.planner_node.timeout or settings.node_execution_timeout
        try:
            response = await asyncio.wait_for(
                model.ainvoke([SystemMessage(content=system_prompt)] + list(messages)),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Planner timed out after %ds", timeout)
            response = AIMessage(content="", tool_calls=[])

        return {
            "messages": [response],
            "agent_hops": agent_hops + 1,
            "current_agent": GraphNode.PLANNER.value,
            "used_plugins": [],
            "error_state": None,
        }

    except Exception as e:
        logger.error("Error in planner node: %s", e, exc_info=True)
        return build_error_state(state, e, GraphNode.PLANNER.value)


async def run_executor_node(
    state: MessageState,
    *,
    tool_node: Any,
    tool_collector: Any,
    settings: Any,
) -> Dict[str, Any]:
    """Execute tool calls and populate attributed tool_results."""
    try:
        timeout = settings.node_execution_timeout

        async def _invoke():
            if hasattr(tool_node, "ainvoke"):
                return await tool_node.ainvoke(state)
            return tool_node.invoke(state)

        try:
            result = await asyncio.wait_for(_invoke(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Executor timed out after %ds", timeout)
            result = {"messages": []}

        tool_messages: List[ToolMessage] = (
            result.get("messages", []) if isinstance(result, dict) else []
        )

        messages = state.get("messages", [])
        last_ai = next(
            (
                m
                for m in reversed(messages)
                if isinstance(m, AIMessage) and m.tool_calls
            ),
            None,
        )

        tool_results: List[Dict[str, Any]] = []
        if last_ai:
            for tool_call in last_ai.tool_calls or []:
                name = (
                    tool_call.get("name")
                    if isinstance(tool_call, dict)
                    else getattr(tool_call, "name", "")
                )
                tool_call_id = (
                    tool_call.get("id")
                    if isinstance(tool_call, dict)
                    else getattr(tool_call, "id", None)
                )
                tool_msg = next(
                    (
                        m
                        for m in tool_messages
                        if isinstance(m, ToolMessage) and m.tool_call_id == tool_call_id
                    ),
                    None,
                )
                data: Any = None
                error: Optional[str] = None
                if tool_msg:
                    try:
                        data = json.loads(tool_msg.content)
                    except (json.JSONDecodeError, TypeError):
                        data = tool_msg.content

                plugin_id = tool_collector.get_plugin_for_tool(name) or ""
                tool_results.append(
                    {
                        "tool_name": name,
                        "plugin_id": plugin_id,
                        "data": data,
                        "error": error,
                    }
                )

        result_dict = result if isinstance(result, dict) else {}
        return {**result_dict, "tool_results": tool_results}

    except Exception as e:
        logger.error("Error in executor node: %s", e, exc_info=True)
        return build_error_state(state, e, GraphNode.EXECUTOR.value)


async def run_synthesizer_node(
    state: MessageState,
    *,
    model: Any,
    settings: Any,
    plugin_bundles: Any,
) -> Dict[str, Any]:
    """Compose final response from tool results."""
    try:
        plugin_desc = build_all_plugins_description(plugin_bundles)
        messages = sanitize_messages(list(state.get("messages", [])))
        tool_results = state.get("tool_results") or []

        template = settings.synthesizer_node.prompt or SupervisorPrompts.SYNTHESIZER
        system_prompt = template.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            plugin_descriptions=plugin_desc,
        )

        stripped = model.without_tools() if hasattr(model, "without_tools") else model

        if tool_results:
            tool_context = "\n".join(
                f"Tool: {r.get('tool_name')} | Plugin: {r.get('plugin_id')}\n{json.dumps(r.get('data'))}"
                for r in tool_results
            )
            context_msg = HumanMessage(content=f"Tool results:\n{tool_context}")
            request_messages = (
                [SystemMessage(content=system_prompt)] + messages + [context_msg]
            )
        else:
            request_messages = [SystemMessage(content=system_prompt)] + messages

        timeout = settings.synthesizer_node.timeout or (
            settings.node_execution_timeout * 2
        )
        try:
            response = await asyncio.wait_for(
                stripped.ainvoke(request_messages),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Synthesizer timed out after %ds", timeout)
            response = AIMessage(
                content="I was unable to complete your request in time. Please try again."
            )

        return {
            "messages": [response],
            "current_agent": GraphNode.SYNTHESIZER.value,
            "error_state": None,
            "tool_results": None,
        }

    except Exception as e:
        logger.error("Error in synthesizer node: %s", e, exc_info=True)
        return build_error_state(state, e, GraphNode.SYNTHESIZER.value)


async def run_clarifier_node(
    state: MessageState,
    *,
    model: Any,
    settings: Any,
    plugin_bundles: Any,
) -> Dict[str, Any]:
    """Ask clarifying questions when intent is unclear or results are insufficient."""
    try:
        messages = sanitize_messages(list(state.get("messages", [])))
        validation_result = state.get("validation_result") or {}
        plugin_desc = build_all_plugins_description(plugin_bundles)

        clarification_type = validation_result.get("clarification_type", [])
        additional_context = build_clarification_context(clarification_type)

        template = settings.clarifier_node.prompt or SupervisorPrompts.CLARIFIER
        system_prompt = template.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            plugin_descriptions=plugin_desc,
            additional_context=additional_context,
        )

        clarifier_messages = build_clarifier_messages(messages, additional_context)
        request_messages = [SystemMessage(content=system_prompt)] + clarifier_messages

        timeout = settings.clarifier_node.timeout or (
            settings.node_execution_timeout * 2
        )
        try:
            response = await asyncio.wait_for(
                model.ainvoke(request_messages),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Clarifier timed out after %ds", timeout)
            response = AIMessage(
                content="Could you please provide more details about your request?"
            )

        return {
            "messages": [response],
            "current_agent": GraphNode.CLARIFIER.value,
            "error_state": None,
        }

    except Exception as e:
        logger.error("Error in clarifier node: %s", e, exc_info=True)
        return build_error_state(state, e, GraphNode.CLARIFIER.value)


async def run_responder_node(
    state: MessageState,
    *,
    model: Any,
    settings: Any,
    plugin_bundles: Any,
) -> Dict[str, Any]:
    """Handle conversational queries (greetings, translation, meta-questions)."""
    try:
        messages = sanitize_messages(list(state.get("messages", [])))
        plugin_desc = build_all_plugins_description(plugin_bundles)

        template = settings.responder_node.prompt or SupervisorPrompts.RESPONDER
        system_prompt = template.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            plugin_descriptions=plugin_desc,
        )

        stripped = model.without_tools() if hasattr(model, "without_tools") else model

        timeout = settings.responder_node.timeout or (
            settings.node_execution_timeout * 2
        )
        try:
            response = await asyncio.wait_for(
                stripped.ainvoke([SystemMessage(content=system_prompt)] + messages),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Responder timed out after %ds", timeout)
            response = AIMessage(
                content="I'm sorry, I was unable to respond in time. Please try again."
            )

        return {
            "messages": [response],
            "current_agent": GraphNode.RESPONDER.value,
            "error_state": None,
        }

    except Exception as e:
        logger.error("Error in responder node: %s", e, exc_info=True)
        return build_error_state(state, e, GraphNode.RESPONDER.value)


async def run_validator_node(
    state: MessageState,
    *,
    model: Any,
    settings: Any,
) -> Dict[str, Any]:
    """Validate tool results against user intent."""
    try:
        messages = list(state.get("messages", []))
        used_plugins = state.get("used_plugins", [])
        tool_results = state.get("tool_results") or []

        if not tool_results:
            return {
                "validation_result": {"passed": True},
                "current_agent": GraphNode.VALIDATOR.value,
            }

        user_query = extract_last_human_query(messages)
        tool_results_text = "\n".join(
            f"Tool Result {result_index + 1}: {json.dumps(tool_result)}"
            for result_index, tool_result in enumerate(tool_results)
        )

        template = settings.validation_node.prompt or SupervisorPrompts.VALIDATION
        system_prompt = template.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            user_query=user_query,
            plugins_used=", ".join(used_plugins),
            tool_results=tool_results_text,
        )

        request_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Please validate the tool results above."),
        ]

        timeout = settings.validation_node.timeout or settings.node_execution_timeout
        try:
            validation_response = await asyncio.wait_for(
                model.ainvoke(request_messages),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Validator timed out after %ds", timeout)
            return {
                "validation_result": {"passed": True},
                "current_agent": GraphNode.VALIDATOR.value,
                "error_state": None,
            }

        from cadence.engine.impl.langgraph.supervisor.core import ValidationResponse

        if isinstance(validation_response, ValidationResponse):
            result = {
                "passed": validation_response.is_valid,
                "reasoning": validation_response.reasoning,
                "query_intent": validation_response.query_intent,
                "clarification_type": validation_response.clarification_type,
                "valid_ids": validation_response.valid_ids,
            }
        else:
            result = {"passed": True}

        return {
            "validation_result": result,
            "current_agent": GraphNode.VALIDATOR.value,
            "error_state": None,
        }

    except Exception as e:
        logger.error("Error in validator node: %s", e, exc_info=True)
        return build_error_state(state, e, GraphNode.VALIDATOR.value)


async def run_error_handler_node(
    state: MessageState,
    *,
    model: Any,
    settings: Any,
) -> Dict[str, Any]:
    """Generate a user-friendly recovery message for any node failure."""
    try:
        messages = list(state.get("messages", []))

        user_query = extract_last_human_query(messages)

        template = settings.error_handler_node.prompt or SupervisorPrompts.ERROR_HANDLER
        system_prompt = template.format(
            current_time=datetime.now(timezone.utc).isoformat(),
            user_query=user_query,
        )

        request_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=f"Help me handle this error gracefully for: {user_query}"
            ),
        ]

        timeout = settings.error_handler_node.timeout or (
            settings.node_execution_timeout * 2
        )
        try:
            response = await asyncio.wait_for(
                model.ainvoke(request_messages),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Error handler timed out after %ds", timeout)
            response = AIMessage(
                content="I apologise, but I encountered an issue processing your request. Please try again."
            )

        return {
            "messages": [response],
            "current_agent": GraphNode.ERROR_HANDLER.value,
            "error_state": None,
        }

    except Exception as e:
        logger.error("Critical: error_handler itself failed: %s", e, exc_info=True)
        fallback = AIMessage(
            content="I apologise, but I encountered an issue processing your request. Please try again."
        )
        return {
            "messages": [fallback],
            "current_agent": GraphNode.ERROR_HANDLER.value,
        }
