# Creating Tools

Tools are the unit of capability in Cadence. Each tool is a `UvTool` — a thin wrapper around a plain Python function or
coroutine. The `@uvtool` decorator is the primary way to create them.

Source files:

- `sdk/src/cadence_sdk/types/sdk_tools.py`
- `sdk/src/cadence_sdk/types/sdk_state.py`

---

## The `@uvtool` decorator

`sdk/src/cadence_sdk/types/sdk_tools.py`

`@uvtool` can be used with or without parentheses. Both forms produce a `UvTool` instance.

```python
from cadence_sdk import uvtool, CacheConfig

# No parentheses — name and description come from the function
@uvtool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return fetch_weather(city)

# With parentheses — override name, set cache, pass extra metadata
@uvtool(name="weather_lookup", cache=True)
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return fetch_weather(city)

# Async function — decorator detects coroutines automatically
@uvtool(cache=CacheConfig(ttl=1800, cache_key_fields=["city"]))
async def get_weather_async(city: str) -> dict:
    """Get weather asynchronously."""
    return await async_fetch_weather(city)
```

### Parameters

| Parameter     | Type                                  | Default                 | Description                                         |
|---------------|---------------------------------------|-------------------------|-----------------------------------------------------|
| `name`        | `str \| None`                         | function name           | Tool name used by the LLM                           |
| `description` | `str \| None`                         | first line of docstring | Tool description passed to the LLM                  |
| `args_schema` | `type[BaseModel] \| None`             | `None`                  | Pydantic model for argument validation              |
| `cache`       | `CacheConfig \| bool \| dict \| None` | `None`                  | Cache configuration (see below)                     |
| `**metadata`  | `Any`                                 | —                       | Arbitrary key/value pairs stored in `tool.metadata` |

The `cache` parameter accepts three forms:

- `True` — enable with default `CacheConfig` settings
- A plain `dict` — passed as kwargs to `CacheConfig(**dict)`
- A `CacheConfig` instance — used directly

Source: `sdk/src/cadence_sdk/types/sdk_tools.py`

---

## UvTool class

`sdk/src/cadence_sdk/types/sdk_tools.py`

```python
class UvTool:
    name: str
    description: str
    func: Callable
    args_schema: Optional[type[BaseModel]]
    cache: Optional[CacheConfig]
    metadata: Dict[str, Any]
    is_async: bool          # set automatically from func
```

`is_async` is derived by calling `asyncio.iscoroutinefunction(func)` in `__init__`.

The decorator also copies `__signature__`, `__doc__`, `__name__`, and `__module__` from the wrapped function onto the
`UvTool` instance so framework adapters can introspect argument types.

### Invocation

```python
# Sync tool — direct call or invoke()
result = my_tool("arg1")
result = my_tool.invoke("arg1")

# Async tool — must use ainvoke()
result = await my_tool.ainvoke("arg1")

# ainvoke() on a sync tool runs it in a thread executor
result = await sync_tool.ainvoke("arg1")   # safe — runs in executor
```

Calling a sync tool via `__call__()` on an async tool raises `RuntimeError` with an informative message.

---

## CacheConfig

`sdk/src/cadence_sdk/types/sdk_tools.py`

```python
@dataclass
class CacheConfig:
    enabled: bool = True
    ttl: int = 3600                       # seconds; default 1 hour
    similarity_threshold: float = 0.85   # 0.0–1.0; higher = stricter match
    cache_key_fields: Optional[List[str]] = None   # None = use all params
```

`similarity_threshold` controls semantic (vector) cache matching. A threshold of `0.85` means only results from queries
that are 85% or more similar to a previous query are reused.

`cache_key_fields` restricts the cache key to a subset of the tool's arguments. This is useful when some arguments are
cosmetic (e.g., a `debug` flag) and should not affect cache lookups.

---

## Tool closure pattern

Tools typically need access to agent state (API keys, configuration). The standard pattern is to define the tool inside
an agent method and capture `self` in the closure:

```python
class WeatherAgent(BaseAgent):
    def __init__(self):
        self._api_key = ""
        self._search_tool = self._build_search_tool()

    def initialize(self, config: dict) -> None:
        self._api_key = config["api_key"]

    def _build_search_tool(self) -> UvTool:
        agent = self   # explicit capture to avoid late-binding pitfalls

        @uvtool
        async def search(query: str) -> dict:
            """Search the web."""
            return await call_api(agent._api_key, query)

        return search

    def get_tools(self):
        return [self._search_tool]
```

The tool is created in `__init__`, before `initialize()` is called. Because the closure captures `agent` (not
`self._api_key` directly), the tool always reads the current value of `_api_key` at call time — even after
`initialize()` sets it.

See `sdk/examples/web_search_agent/plugin.py` for a real-world example.

---

## Sync tool example

```python
from cadence_sdk import uvtool

@uvtool
def calculate_tax(amount: float, rate: float = 0.2) -> float:
    """Calculate tax on an amount at the given rate."""
    return round(amount * rate, 2)

# Verify
assert calculate_tax.is_async is False
result = calculate_tax(100.0, rate=0.15)   # 15.0
```

---

## Async tool example

```python
import httpx
from cadence_sdk import uvtool

@uvtool(name="fetch_page")
async def fetch_page(url: str) -> str:
    """Fetch the text content of a web page."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        return response.text

# Verify
assert fetch_page.is_async is True
content = await fetch_page.ainvoke(url="https://example.com")
```

---

## Tool with CacheConfig and args_schema

```python
from pydantic import BaseModel, Field
from cadence_sdk import uvtool, CacheConfig

class SearchInput(BaseModel):
    query: str = Field(description="The search query")
    max_results: int = Field(default=10, description="Maximum results to return")

@uvtool(
    args_schema=SearchInput,
    cache=CacheConfig(
        enabled=True,
        ttl=3600,
        similarity_threshold=0.9,
        cache_key_fields=["query"],   # max_results excluded from cache key
    ),
)
async def web_search(query: str, max_results: int = 10) -> list:
    """Search the web and return organic results."""
    return await call_search_api(query, max_results)
```

---

## UvState

`sdk/src/cadence_sdk/types/sdk_state.py`

```python
class UvState(TypedDict, total=False):
    messages: List[AnyMessage]
    thread_id: Optional[str]
```

This is the minimal shared state contract. Framework adapters extend it with routing history, agent hop counters, and
error flags — those fields are not part of the SDK contract and are not documented here.

---

See also:

- [Plugin Development](plugin-development.md) — how tools are returned from `get_tools()`
- [Plugin Settings](settings.md) — passing API keys into tool closures via `initialize(config)`
