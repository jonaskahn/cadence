# Testing

## Testing Framework

- **Pytest** for unit and integration tests
- **pytest-asyncio** for async test support
- **pytest-cov** for coverage reporting
- **pytest-mock** for mocking external dependencies

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=cadence

# Run specific test file
poetry run pytest tests/test_plugin_manager.py

# Run with verbose output
poetry run pytest -v

# Run only unit tests
poetry run pytest tests/unit/

# Run only integration tests
poetry run pytest tests/integration/
```

## Test Structure

```
tests/
├── unit/                 # Unit tests for individual components
│   ├── test_plugin_manager.py
│   ├── test_llm_factory.py
│   └── test_orchestrator.py
├── integration/          # Integration tests for component interactions
│   ├── test_plugin_loading.py
│   ├── test_conversation_flow.py
│   └── test_api_endpoints.py
├── fixtures/             # Test fixtures and data
│   ├── conftest.py
│   └── sample_plugins.py
└── e2e/                  # End-to-end tests
    ├── test_full_workflow.py
    └── test_plugin_upload.py
```

## Writing Tests

### Unit Tests

Test individual components in isolation:

```python
import pytest
from cadence.core.services import PluginManager

def test_plugin_discovery():
    manager = PluginManager()
    plugins = manager.discover_plugins()
    assert len(plugins) > 0

def test_plugin_validation():
    manager = PluginManager()
    result = manager.validate_plugin(plugin_data)
    assert result.is_valid
```

### Integration Tests

Test component interactions:

```python
import pytest
from cadence.main import CadenceApplication

@pytest.mark.asyncio
async def test_plugin_loading_integration():
    app = CadenceApplication()
    await app.initialize()

    plugins = app.plugin_manager.get_available_plugins()
    assert len(plugins) > 0
```

### Plugin Testing

Validate plugin behavior:

```python
def test_plugin_metadata():
    plugin = MathPlugin()
    metadata = plugin.get_metadata()

    assert metadata.name == "mathematics"
    assert "addition" in metadata.capabilities
    assert metadata.version is not None

def test_plugin_health_check():
    plugin = MathPlugin()
    health = plugin.health_check()

    assert health["healthy"] is True
    assert "details" in health
```

## Test Configuration

### pytest.ini

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --strict-config
    --cov=cadence
    --cov-report=html
    --cov-report=term-missing
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
```

### Test Environment

```python
# conftest.py
import pytest
import asyncio
from cadence.main import CadenceApplication

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def app():
    """Create a test application instance."""
    app = CadenceApplication()
    await app.initialize()
    yield app
    await app.cleanup()
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.13]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install Poetry
        uses: snok/install-poetry@v1

      - name: Install dependencies
        run: poetry install

      - name: Run tests
        run: poetry run pytest --cov=cadence --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Best Practices

1. **Test Naming**: Use descriptive test names that explain what is being tested
2. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
3. **Mocking**: Mock external dependencies to isolate units under test
4. **Fixtures**: Use pytest fixtures for common test setup
5. **Coverage**: Aim for high test coverage, especially for critical paths
6. **Async Testing**: Use `pytest-asyncio` for testing async code
7. **Plugin Testing**: Test plugin metadata, health checks, and tool functionality
8. **Error Cases**: Test both success and failure scenarios
9. **Performance**: Include performance tests for critical operations
10. **Documentation**: Document complex test scenarios and test data
