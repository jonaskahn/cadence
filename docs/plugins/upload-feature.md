# Plugin Upload Feature

This document describes the new plugin upload functionality in Cadence, which allows users to upload plugin packages as ZIP files and have them automatically loaded into the system.

## Overview

The plugin upload feature provides a user-friendly way to install new plugins without manual file system operations. Users can upload plugin packages through the web interface, and the system will automatically validate, extract, and load them.

## Features

- **ZIP File Upload**: Upload plugin packages in ZIP format
- **Automatic Validation**: Validate plugin structure and dependencies
- **Version Management**: Support for plugin versioning (name-version.zip format)
- **Force Overwrite**: Option to overwrite existing plugins
- **Automatic Reload**: Plugins are automatically reloaded after upload
- **Archive Storage**: Original ZIP files are stored for backup
- **Plugin Management**: List, view, and delete uploaded plugins

## Configuration

The feature uses two new configuration settings:

```python
store_plugin: str = "./store_plugin"      # Directory to store extracted plugins
store_archived: str = "./store_archived"  # Directory to store uploaded archives
```

These can be configured via environment variables:

- `CADENCE_STORE_PLUGIN`
- `CADENCE_STORE_ARCHIVED`

## File Naming Convention

Plugins must follow the naming convention: `name-version.zip`

Examples:

- `math_agent-1.0.0.zip`
- `search_plugin-2.1.3.zip`
- `my_custom_plugin-0.1.0.zip`

## Plugin Structure Requirements

Uploaded plugins must have the following structure:

```
plugin_name/
├── __init__.py          # Required: Package initialization
├── plugin.py            # Required: Main plugin file
└── [optional files]     # Additional plugin files
```

## API Endpoints

### Upload Plugin

```
POST /api/v1/plugins/plugins/upload
```

Parameters:

- `file`: ZIP file (multipart/form-data)
- `force_overwrite`: Boolean (optional, default: false)

### List Uploaded Plugins

```
GET /api/v1/plugins/plugins/uploaded
```

### Delete Uploaded Plugin

```
DELETE /api/v1/plugins/plugins/uploaded/{plugin_name}/{plugin_version}
```

## Web Interface

The web interface provides:

1. **Upload Section**: File uploader with force overwrite option
2. **Uploaded Plugins List**: View all uploaded plugins with delete options
3. **Plugin Operations**: Refresh and manage existing plugins

## Usage Example

1. **Prepare Plugin**: Create a plugin following the Cadence SDK structure
2. **Package Plugin**: Zip the plugin directory with name-version.zip format
3. **Upload**: Use the web interface to upload the ZIP file
4. **Verify**: Check that the plugin appears in the uploaded plugins list
5. **Test**: Use the plugin in conversations

## Testing

A test plugin is included in the `test_plugin/` directory. To create a test ZIP file:

```bash
python create_test_plugin.py
```

This creates `test_plugin-1.0.0.zip` which can be used to test the upload functionality.

## Error Handling

The system provides comprehensive error handling:

- **File Validation**: Checks file format and size
- **Structure Validation**: Validates plugin directory structure
- **Dependency Validation**: Checks plugin dependencies
- **Installation Validation**: Verifies successful installation
- **Cleanup**: Removes files on failed uploads

## Security Considerations

- File size limit: 50MB maximum
- File type restriction: Only ZIP files allowed
- Temporary file cleanup: Uploaded files are cleaned up on failure
- Validation: All plugins are validated before installation

## Troubleshooting

### Common Issues

1. **Invalid filename format**: Ensure filename follows `name-version.zip` pattern
2. **Missing required files**: Ensure `__init__.py` and `plugin.py` exist
3. **Plugin already exists**: Use force overwrite option or delete existing plugin
4. **Validation errors**: Check plugin structure and dependencies

### Debug Information

The system logs detailed information about:

- Upload progress
- Validation results
- Installation status
- Error details

Check the application logs for detailed error information.

## Future Enhancements

Potential future improvements:

- Plugin dependency resolution
- Plugin update notifications
- Plugin marketplace integration
- Plugin version compatibility checking
- Plugin backup and restore
- Plugin sharing between instances
