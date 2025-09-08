# Plugin Upload Feature

The Cadence framework provides comprehensive plugin upload and management capabilities through both UI and API
interfaces. This feature allows you to dynamically add, manage, and monitor plugins without modifying the core system.

## Overview

The plugin upload system enables:

- **Dynamic Plugin Installation**: Upload ZIP-packaged plugins at runtime
- **Version Management**: Handle multiple versions of the same plugin
- **Dependency Resolution**: Automatic installation of plugin dependencies
- **Health Monitoring**: Real-time plugin health checks and validation
- **Hot Reloading**: Activate new plugins without system restart

## Plugin Package Format

Plugins must be packaged as ZIP files following the naming convention: `{plugin_name}-{version}.zip`

### Example Package Structure

```
math_plugin-1.0.0.zip
├── __init__.py          # Plugin registration
├── plugin.py            # Main plugin class
├── agent.py             # Agent implementation
├── tools.py             # Tool functions
├── pyproject.toml       # Package configuration (optional)
└── README.md            # Documentation (optional)
```

### Required Files

1. **`__init__.py`**: Must register the plugin with the SDK

   ```python
   from cadence_sdk import register_plugin
   from .plugin import MyPlugin

   register_plugin(MyPlugin)
   ```

2. **`plugin.py`**: Plugin class implementing `BasePlugin`
3. **`agent.py`**: Agent class implementing `BaseAgent`
4. **`tools.py`**: Tool implementations using `@tool` decorator

## Upload Methods

### 1. UI-Based Upload (Streamlit Interface)

The Streamlit UI provides an intuitive interface for plugin management:

#### Features:

- **Drag-and-Drop Upload**: Simply drag ZIP files to upload
- **Force Overwrite**: Option to replace existing plugins
- **Upload Progress**: Real-time upload status and feedback
- **Plugin List**: View all uploaded plugins with metadata
- **Plugin Deletion**: Remove uploaded plugins with confirmation
- **Health Status**: Visual indicators for plugin health

#### Steps:

1. Access the Cadence UI at `http://localhost:8501`
2. Navigate to the "Plugin Management" section in the sidebar
3. Use the file uploader to select your plugin ZIP file
4. Check "Force overwrite" if replacing an existing plugin
5. Click "Upload Plugin" to install
6. Monitor the upload progress and results

### 2. API-Based Upload (REST Endpoints)

For programmatic plugin management, use the REST API endpoints:

#### Upload Plugin

```bash
curl -X POST "http://localhost:8000/api/v1/plugins/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@math_plugin-1.0.0.zip" \
  -F "force_overwrite=false"
```

**Response:**

```json
{
  "success": true,
  "message": "Plugin uploaded and loaded successfully",
  "plugin_name": "math_plugin",
  "plugin_version": "1.0.0",
  "details": {
    "extracted_to": "/path/to/store_plugin/math_plugin-1.0.0",
    "validation": "passed",
    "dependencies_installed": ["numpy>=1.20.0"]
  }
}
```

#### List Uploaded Plugins

```bash
curl -X GET "http://localhost:8000/api/v1/plugins/uploaded"
```

**Response:**

```json
{
  "success": true,
  "plugins": [
    {
      "name": "math_plugin",
      "version": "1.0.0",
      "directory": "/path/to/store_plugin/math_plugin-1.0.0"
    }
  ]
}
```

#### Delete Uploaded Plugin

```bash
curl -X DELETE "http://localhost:8000/api/v1/plugins/uploaded/math_plugin/1.0.0"
```

## Plugin Storage

### Directory Structure

Uploaded plugins are stored in the configured plugin store directory:

```
store_plugin/                    # CADENCE_STORE_PLUGIN
├── math_plugin-1.0.0/          # Extracted plugin
│   ├── __init__.py
│   ├── plugin.py
│   ├── agent.py
│   └── tools.py
└── search_plugin-2.1.0/        # Another plugin
    ├── __init__.py
    ├── plugin.py
    ├── agent.py
    └── tools.py

store_archived/                  # CADENCE_STORE_ARCHIVED
├── math_plugin-1.0.0.zip       # Original ZIP files
└── search_plugin-2.1.0.zip
```

### Configuration

Configure plugin storage directories via environment variables:

```bash
# Plugin storage directory
CADENCE_STORE_PLUGIN=./store_plugin

# Archive directory for ZIP files
CADENCE_STORE_ARCHIVED=./store_archived

# Enable directory-based plugin discovery
CADENCE_ENABLE_DIRECTORY_PLUGINS=true
```

## Plugin Validation

The upload system performs comprehensive validation:

### 1. Structure Validation

- Verifies required files exist (`__init__.py`, `plugin.py`, etc.)
- Checks plugin registration in `__init__.py`
- Validates class inheritance (`BasePlugin`, `BaseAgent`)

### 2. Metadata Validation

- Plugin name and version format
- Required metadata fields
- Capability declarations
- LLM requirements

### 3. Dependency Validation

- Checks declared dependencies
- Attempts automatic installation
- Validates import statements

### 4. Health Checks

- Executes plugin health check methods
- Validates tool functionality
- Checks external service connectivity

## Error Handling

### Common Upload Errors

1. **Invalid ZIP Format**

   ```json
   {
     "success": false,
     "message": "Invalid ZIP file format",
     "details": "File is not a valid ZIP archive"
   }
   ```

2. **Missing Required Files**

   ```json
   {
     "success": false,
     "message": "Plugin validation failed",
     "details": "Missing required file: plugin.py"
   }
   ```

3. **Dependency Installation Failed**

   ```json
   {
     "success": false,
     "message": "Dependency installation failed",
     "details": "Failed to install: numpy>=1.20.0"
   }
   ```

4. **Plugin Already Exists**
   ```json
   {
     "success": false,
     "message": "Plugin already exists",
     "plugin_name": "math_plugin",
     "plugin_version": "1.0.0",
     "details": "Use force_overwrite=true to replace"
   }
   ```

## Plugin Management Workflow

### Development Workflow

1. **Develop Plugin**: Create plugin following SDK guidelines
2. **Package Plugin**: Create ZIP file with proper naming
3. **Upload Plugin**: Use UI or API to upload
4. **Test Plugin**: Verify functionality through chat interface
5. **Monitor Health**: Check plugin status and performance
6. **Update Plugin**: Upload new version when ready

### Production Workflow

1. **Stage Plugin**: Test in development environment
2. **Package Release**: Create production-ready ZIP package
3. **Deploy Plugin**: Upload to production system
4. **Health Monitoring**: Continuous monitoring of plugin status
5. **Rollback**: Remove or replace if issues occur

## Integration with Core System

### Automatic Discovery

Uploaded plugins are automatically integrated into the plugin discovery system:

1. **Extraction**: ZIP files extracted to plugin store directory
2. **Registration**: Plugin classes registered with SDK registry
3. **Validation**: Comprehensive validation and health checks
4. **Loading**: Plugin bundles created and integrated
5. **Graph Integration**: LangGraph nodes and edges configured
6. **Activation**: Plugin becomes available for conversations

### Hot Reloading

The system supports hot reloading of plugins:

- **No Downtime**: Upload plugins without stopping the system
- **Automatic Refresh**: Plugin list updates automatically
- **State Preservation**: Existing conversations continue unaffected
- **Rollback Support**: Easy removal of problematic plugins

## Best Practices

### Plugin Development

1. **Follow SDK Guidelines**: Use proper base classes and decorators
2. **Comprehensive Testing**: Test plugins before packaging
3. **Dependency Management**: Declare all dependencies explicitly
4. **Error Handling**: Implement robust error handling
5. **Documentation**: Include clear documentation and examples
6. **Parallel Tool Calls**: Configure `parallel_tool_calls` parameter in BaseAgent constructor for optimal performance

#### Parallel Tool Calls Configuration

When developing plugins for upload, consider the parallel tool calls feature for optimal performance:

```python
from cadence_sdk import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, metadata):
        # Enable parallel tool calls for concurrent execution
        super().__init__(metadata, parallel_tool_calls=True)

    # For agents with dependent decorators, disable parallel execution
    # super().__init__(metadata, parallel_tool_calls=False)
```

**Benefits for Uploaded Plugins:**

- **Faster Response Times**: Multiple tools execute simultaneously
- **Better Resource Utilization**: Efficient handling of I/O operations
- **Improved Scalability**: Better performance under load
- **Enhanced User Experience**: Quicker plugin responses

### Packaging

1. **Semantic Versioning**: Use proper version numbering
2. **Clean Structure**: Organize files logically
3. **Minimal Dependencies**: Only include necessary dependencies
4. **Test Package**: Verify ZIP structure before upload

### Deployment

1. **Staging Environment**: Test uploads in staging first
2. **Backup Strategy**: Keep backups of working plugins
3. **Monitoring**: Monitor plugin health after deployment
4. **Gradual Rollout**: Test with limited users first

## Security Considerations

### Upload Security

- **File Validation**: ZIP files are validated before extraction
- **Path Traversal Protection**: Prevents malicious file paths
- **Size Limits**: Configurable upload size limits
- **Content Scanning**: Basic content validation

### Runtime Security

- **Sandboxing**: Plugins run in controlled environment
- **Resource Limits**: CPU and memory limits per plugin
- **Network Restrictions**: Control external network access
- **Logging**: Comprehensive audit logging

## Troubleshooting

### Upload Issues

1. **Check File Format**: Ensure proper ZIP format
2. **Verify Structure**: Check required files exist
3. **Review Logs**: Check application logs for details
4. **Test Locally**: Test plugin structure locally first

### Runtime Issues

1. **Health Checks**: Use health check endpoints
2. **Plugin Status**: Monitor plugin status in UI
3. **Dependency Issues**: Check dependency installation
4. **Reload Plugins**: Use reload functionality if needed

## API Reference

### Upload Plugin

- **Endpoint**: `POST /api/v1/plugins/upload`
- **Content-Type**: `multipart/form-data`
- **Parameters**: `file` (ZIP file), `force_overwrite` (boolean)

### List Uploaded Plugins

- **Endpoint**: `GET /api/v1/plugins/uploaded`
- **Response**: List of uploaded plugin metadata

### Delete Plugin

- **Endpoint**: `DELETE /api/v1/plugins/uploaded/{name}/{version}`
- **Parameters**: `name` (plugin name), `version` (plugin version)

### Reload Plugins

- **Endpoint**: `POST /api/v1/plugins/reload`
- **Effect**: Reloads all plugins including uploaded ones

## Examples

### Simple Plugin Upload

```python
import requests

# Upload plugin via API
with open('my_plugin-1.0.0.zip', 'rb') as f:
    files = {'file': f}
    data = {'force_overwrite': 'false'}
    response = requests.post(
        'http://localhost:8000/api/v1/plugins/upload',
        files=files,
        data=data
    )

print(response.json())
```

### Batch Plugin Management

```python
import requests
import os

def upload_plugins_from_directory(directory):
    """Upload all ZIP files from a directory."""
    for filename in os.listdir(directory):
        if filename.endswith('.zip'):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'rb') as f:
                files = {'file': f}
                data = {'force_overwrite': 'true'}
                response = requests.post(
                    'http://localhost:8000/api/v1/plugins/upload',
                    files=files,
                    data=data
                )
                print(f"{filename}: {response.json()}")

# Upload all plugins from directory
upload_plugins_from_directory('./plugin_packages/')
```

## Conclusion

The plugin upload feature provides a powerful and flexible way to extend Cadence functionality without modifying the
core system. By supporting both UI and API-based management, it accommodates different deployment scenarios and
workflows while maintaining system stability and security.

For more information on plugin development, see the [Plugin Development Overview](overview.md)
and [Creating Your First Plugin](first-plugin.md) guides.
