"""Constants for coordinator functionality."""


class GraphNodeNames:
    """Names of nodes in the conversation graph."""

    COORDINATOR = "coordinator"
    CONTROL_TOOLS = "control_tools"
    SUSPEND = "suspend"
    SYNTHESIZER = "synthesizer"


class RoutingDecision:
    """Possible routing decisions in the conversation flow."""

    CONTINUE = "continue"
    SUSPEND = "suspend"
    DONE = "done"
    TERMINATE = "terminate"
