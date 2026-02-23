"""Graph node identity and display metadata for the LangGraph supervisor."""

from __future__ import annotations

import random
from enum import Enum
from typing import Dict


class GraphNode(Enum):
    ROUTER = "router"
    PLANNER = "planner"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
    SYNTHESIZER = "synthesizer"
    CLARIFIER = "clarifier"
    RESPONDER = "responder"
    ERROR_HANDLER = "error_handler"
    END = "end"

    @classmethod
    def values(cls) -> set[str]:
        return {m.value for m in cls}


class NodeDisplay:
    _META: Dict[GraphNode, Dict] = {
        GraphNode.ROUTER: {
            "key": "msg.orchestrator.router",
            "progress_range": (1, 1),
            "fallback": "Thinking",
        },
        GraphNode.PLANNER: {
            "key": "msg.orchestrator.planner",
            "progress_range": (15, 25),
            "fallback": "Planning",
        },
        GraphNode.EXECUTOR: {
            "key": "msg.orchestrator.executor",
            "progress_range": (30, 40),
            "fallback": "Gathering resources",
        },
        GraphNode.VALIDATOR: {
            "key": "msg.orchestrator.validator",
            "progress_range": (50, 65),
            "fallback": "Validating results",
        },
        GraphNode.SYNTHESIZER: {
            "key": "msg.orchestrator.synthesizer",
            "progress_range": (80, 95),
            "fallback": "Generate answer",
        },
        GraphNode.CLARIFIER: {
            "key": "msg.orchestrator.clarifier",
            "progress_range": (80, 95),
            "fallback": "Generate answer",
        },
        GraphNode.RESPONDER: {
            "key": "msg.orchestrator.responder",
            "progress_range": (80, 95),
            "fallback": "Generate answer",
        },
        GraphNode.ERROR_HANDLER: {
            "key": "msg.orchestrator.error_handler",
            "progress_range": (80, 95),
            "fallback": "Generate answer",
        },
        GraphNode.END: {
            "key": "msg.orchestrator.end",
            "progress_range": (100, 100),
            "fallback": "Finished",
        },
    }

    @classmethod
    def _resolve(cls, meta: Dict) -> Dict:
        low, high = meta["progress_range"]
        result = {**meta, "progress": random.randint(low, high)}
        del result["progress_range"]
        return result

    @classmethod
    def get(cls, node: GraphNode) -> Dict:
        meta = cls._META.get(node)
        return cls._resolve(meta) if meta else {}

    @classmethod
    def get_by_name(cls, node_name: str) -> Dict:
        for node, meta in cls._META.items():
            if node.value == node_name:
                return cls._resolve(meta)
        return {}

    @classmethod
    def token_streaming_nodes(cls) -> set[str]:
        return {
            GraphNode.SYNTHESIZER.value,
            GraphNode.CLARIFIER.value,
            GraphNode.RESPONDER.value,
            GraphNode.ERROR_HANDLER.value,
        }

    @classmethod
    def to_convenience_dict(cls) -> Dict[str, Dict]:
        return {node.value: cls._resolve(meta) for node, meta in cls._META.items()}
