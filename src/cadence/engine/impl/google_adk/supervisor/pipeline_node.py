"""Pipeline node identity and display metadata for the Google ADK supervisor."""

from __future__ import annotations

import random
from enum import Enum
from typing import Dict


class PipelineNode(Enum):
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
    _META: Dict[PipelineNode, Dict] = {
        PipelineNode.ROUTER: {
            "key": "msg.orchestrator.router",
            "progress_range": (1, 1),
            "fallback": "Thinking",
        },
        PipelineNode.PLANNER: {
            "key": "msg.orchestrator.planner",
            "progress_range": (15, 25),
            "fallback": "Planning",
        },
        PipelineNode.EXECUTOR: {
            "key": "msg.orchestrator.executor",
            "progress_range": (30, 40),
            "fallback": "Gathering resources",
        },
        PipelineNode.VALIDATOR: {
            "key": "msg.orchestrator.validator",
            "progress_range": (50, 65),
            "fallback": "Validating results",
        },
        PipelineNode.SYNTHESIZER: {
            "key": "msg.orchestrator.synthesizer",
            "progress_range": (80, 95),
            "fallback": "Generate answer",
        },
        PipelineNode.CLARIFIER: {
            "key": "msg.orchestrator.clarifier",
            "progress_range": (80, 95),
            "fallback": "Generate answer",
        },
        PipelineNode.RESPONDER: {
            "key": "msg.orchestrator.responder",
            "progress_range": (80, 95),
            "fallback": "Generate answer",
        },
        PipelineNode.ERROR_HANDLER: {
            "key": "msg.orchestrator.error_handler",
            "progress_range": (80, 95),
            "fallback": "Generate answer",
        },
        PipelineNode.END: {
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
    def get(cls, node: PipelineNode) -> Dict:
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
            PipelineNode.SYNTHESIZER.value,
            PipelineNode.CLARIFIER.value,
            PipelineNode.RESPONDER.value,
            PipelineNode.ERROR_HANDLER.value,
        }

    @classmethod
    def to_convenience_dict(cls) -> Dict[str, Dict]:
        return {node.value: cls._resolve(meta) for node, meta in cls._META.items()}
