# Code Style

## Code Formatting

We use automated tools to maintain consistent code style:

- **Black** for code formatting
- **Isort** for import sorting
- **MyPy** for type checking
- **Ruff** for linting and additional checks

## Running Code Quality Tools

```bash
# Format code with Black
poetry run black .

# Sort imports with Isort
poetry run isort .

# Type check with MyPy
poetry run mypy .

# Lint with Ruff
poetry run ruff check .

# Fix auto-fixable issues
poetry run ruff check --fix .
```

## Configuration

### Black Configuration

```toml
# pyproject.toml
[tool.black]
line-length = 120
target-version = ["py313"]
```

### Isort Configuration

```toml
# pyproject.toml
[tool.isort]
profile = "black"
line_length = 120
```

### MyPy Configuration

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.13"
strict = true
```

### Ruff Configuration

```toml
# pyproject.toml
[tool.ruff]
target-version = "py313"
line-length = 120
```

## Style Guidelines

### General Principles

1. **High-verbosity, readable code**: Prefer explicit over implicit
2. **Avoid ambiguous names**: Use descriptive variable and function names
3. **Keep functions small and focused**: Single responsibility principle
4. **Use type hints**: All public functions should have type annotations
5. **Document complex logic**: Add docstrings for classes and functions

### Naming Conventions

- **Variables**: `snake_case` (e.g., `plugin_manager`, `conversation_id`)
- **Functions**: `snake_case` (e.g., `get_plugin_metadata`, `validate_dependencies`)
- **Classes**: `PascalCase` (e.g., `PluginManager`, `ConversationService`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_AGENT_HOPS`, `DEFAULT_TEMPERATURE`)
- **Private methods**: `_snake_case` (e.g., `_validate_plugin`, `_load_configuration`)

### Function Guidelines

```python
def process_conversation_message(
    message: str,
    user_id: str,
    org_id: str,
    tone: str = "natural"
) -> ConversationResponse:
    """
    Process a conversation message through the multi-agent system.

    Args:
        message: The user's message content
        user_id: Unique identifier for the user
        org_id: Organization identifier
        tone: Response tone preference

    Returns:
        ConversationResponse with the processed result

    Raises:
        ValidationError: If message format is invalid
        ProcessingError: If message processing fails
    """
    # Implementation here
    pass
```

### Class Guidelines

```python
class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self, config: PluginConfig):
        """Initialize the plugin manager with configuration."""
        self.config = config
        self._plugins: Dict[str, PluginBundle] = {}
        self._initialized = False

    def discover_plugins(self) -> List[PluginBundle]:
        """
        Discover available plugins from configured sources.

        Returns:
            List of discovered plugin bundles

        Raises:
            DiscoveryError: If plugin discovery fails
        """
        # Implementation here
        pass
```

### Import Organization

```python
# Standard library imports
import asyncio
import logging
from typing import Dict, List, Optional

# Third-party imports
from fastapi import APIRouter, Depends
from pydantic import BaseModel

# Local imports
from cadence.core.services import PluginManager
from cadence.domain.models import Conversation
from cadence.infrastructure.database import DatabaseFactory
```

### Error Handling

```python
def load_plugin(plugin_path: str) -> PluginBundle:
    """Load a plugin from the specified path."""
    try:
        plugin_module = importlib.import_module(plugin_path)
        plugin_class = getattr(plugin_module, "Plugin")
        return PluginBundle(plugin_class())
    except ImportError as e:
        logger.error(f"Failed to import plugin from {plugin_path}: {e}")
        raise PluginLoadError(f"Could not import plugin: {e}") from e
    except AttributeError as e:
        logger.error(f"Plugin {plugin_path} missing required Plugin class: {e}")
        raise PluginLoadError(f"Invalid plugin structure: {e}") from e
```

### Type Hints

```python
from typing import Dict, List, Optional, Union, Any
from typing_extensions import TypedDict

class PluginMetadata(TypedDict):
    """Plugin metadata structure."""
    name: str
    version: str
    description: str
    capabilities: List[str]
    llm_requirements: Dict[str, Any]

def get_plugin_info(plugin_id: str) -> Optional[PluginMetadata]:
    """Get plugin information by ID."""
    # Implementation here
    pass

async def process_async_operation(
    data: List[Dict[str, Any]],
    callback: Optional[callable] = None
) -> Union[Dict[str, Any], None]:
    """Process data asynchronously with optional callback."""
    # Implementation here
    pass
```

## Pre-commit Hooks

Set up pre-commit hooks to automatically run code quality checks:

```bash
# Install pre-commit
poetry run pre-commit install

# Run pre-commit on all files
poetry run pre-commit run --all-files
```

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 25.1.0
    hooks:
      - id: black
        language_version: python3.13

  - repo: https://github.com/pycqa/isort
    rev: 6.0.1
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.17.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: 0.12.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
```

## IDE Configuration

### VS Code Settings

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "python.linting.ruffEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### PyCharm Settings

1. Install Black and isort plugins
2. Configure Black as code formatter
3. Enable MyPy type checking
4. Set up import optimization

## Code Review Guidelines

1. **Check formatting**: Ensure code follows Black/isort formatting
2. **Verify type hints**: All public functions should have type annotations
3. **Review naming**: Variable and function names should be descriptive
4. **Check documentation**: Complex functions should have docstrings
5. **Validate error handling**: Proper exception handling and logging
6. **Test coverage**: New code should have corresponding tests
7. **Performance**: Consider performance implications of changes
8. **Security**: Review for potential security issues
