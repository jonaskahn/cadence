"""Engine-specific constants for orchestration tiers, nodes, and defaults."""

# Orchestration tier names
HOT_TIER = "hot"
WARM_TIER = "warm"
COLD_TIER = "cold"

# LangGraph node names
TOOLS_NODE = "tools"
SYNTHESIZER_NODE = "synthesizer"

# Framework identifiers
LANGGRAPH_FRAMEWORK = "langgraph"

# Factory registry keys
FACTORY_KEY_ADAPTER = "adapter_class"
FACTORY_KEY_ORCHESTRATOR = "orchestrator_class"
FACTORY_KEY_STREAMING = "streaming_wrapper_class"

# Multi-tier pool defaults
DEFAULT_MAX_HOT_POOL_SIZE = 200
DEFAULT_WARM_TIER_TTL = 3600

# Mode configuration defaults
DEFAULT_MAX_AGENT_HOPS = 15
DEFAULT_CONSECUTIVE_ROUTE_LIMIT = 3
DEFAULT_INVOKE_TIMEOUT = 120
DEFAULT_MAX_HANDOFFS = 10
