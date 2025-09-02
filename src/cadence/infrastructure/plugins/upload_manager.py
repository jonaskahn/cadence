"""Plugin Upload Manager for Cadence Framework.

This module provides functionality for uploading, validating, and installing plugin packages
from zip files. It handles the complete lifecycle of plugin uploads including archive storage,
validation, and integration with the existing plugin system.
"""

import os
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

from ...config.settings import settings
from .sdk_manager import SDKPluginManager


class PluginUploadResult(BaseModel):
    """Result of a plugin upload operation."""

    success: bool
    plugin_name: Optional[str] = None
    plugin_version: Optional[str] = None
    message: str
    details: Optional[Dict] = None


class PluginUploadManager:
    """Manages plugin uploads, validation, and installation."""

    def __init__(self, plugin_manager: SDKPluginManager):
        self.plugin_manager = plugin_manager
        self.store_plugin_dir = Path(settings.store_plugin)
        self.store_archived_dir = Path(settings.store_archived)

        # Ensure directories exist
        self.store_plugin_dir.mkdir(parents=True, exist_ok=True)
        self.store_archived_dir.mkdir(parents=True, exist_ok=True)

    def upload_plugin(self, file: UploadFile, force_overwrite: bool = False) -> PluginUploadResult:
        """Upload and install a plugin from a zip file.

        Args:
            file: The uploaded zip file
            force_overwrite: Whether to overwrite existing plugin

        Returns:
            PluginUploadResult with upload status and details
        """
        try:
            # Validate file
            if not self._validate_upload_file(file):
                return PluginUploadResult(success=False, message="Invalid file format. Only ZIP files are supported.")

            # Extract plugin name and version from filename
            plugin_name, plugin_version = self._parse_plugin_filename(file.filename)
            if not plugin_name or not plugin_version:
                return PluginUploadResult(success=False, message="Invalid filename format. Expected: name-version.zip")

            # Check if plugin already exists
            if not force_overwrite and self._plugin_exists(plugin_name, plugin_version):
                return PluginUploadResult(
                    success=False,
                    plugin_name=plugin_name,
                    plugin_version=plugin_version,
                    message=f"Plugin {plugin_name}-{plugin_version} already exists. Use force_overwrite=True to replace.",
                )

            # Save archive
            archive_path = self._save_archive(file, plugin_name, plugin_version)

            # Extract and validate plugin
            plugin_dir = self._extract_plugin(archive_path, plugin_name, plugin_version)

            # Validate plugin structure
            validation_result = self._validate_plugin_structure(plugin_dir)
            if not validation_result["valid"]:
                # Clean up on validation failure
                self._cleanup_failed_upload(plugin_dir, archive_path)
                return PluginUploadResult(
                    success=False,
                    plugin_name=plugin_name,
                    plugin_version=plugin_version,
                    message="Plugin validation failed",
                    details=validation_result,
                )

            # Install plugin
            install_result = self._install_plugin(plugin_dir, plugin_name, plugin_version)
            if not install_result["success"]:
                # Clean up on installation failure
                self._cleanup_failed_upload(plugin_dir, archive_path)
                return PluginUploadResult(
                    success=False,
                    plugin_name=plugin_name,
                    plugin_version=plugin_version,
                    message="Plugin installation failed",
                    details=install_result,
                )

            # Reload plugin manager
            self.plugin_manager.reload_plugins()

            return PluginUploadResult(
                success=True,
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                message=f"Plugin {plugin_name}-{plugin_version} uploaded and installed successfully",
                details={
                    "archive_path": str(archive_path),
                    "plugin_dir": str(plugin_dir),
                    "validation": validation_result,
                    "installation": install_result,
                },
            )

        except Exception as e:
            return PluginUploadResult(success=False, message=f"Upload failed: {str(e)}")

    def _validate_upload_file(self, file: UploadFile) -> bool:
        """Validate the uploaded file."""
        if not file.filename:
            return False

        # Check file extension
        if not file.filename.lower().endswith(".zip"):
            return False

        # Check file size (max 50MB)
        if hasattr(file, "size") and file.size and file.size > 50 * 1024 * 1024:
            return False

        return True

    def _parse_plugin_filename(self, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse plugin name and version from filename.

        Expected format: name-version.zip
        """
        if not filename or not filename.endswith(".zip"):
            return None, None

        # Remove .zip extension
        base_name = filename[:-4]

        # Split by last dash to separate name and version
        if "-" not in base_name:
            return None, None

        # Find the last dash to handle names that might contain dashes
        last_dash_index = base_name.rfind("-")
        if last_dash_index == 0:  # Only dash at beginning
            return None, None

        plugin_name = base_name[:last_dash_index]
        plugin_version = base_name[last_dash_index + 1 :]

        # Additional validation: ensure we have both name and version
        if not plugin_name or not plugin_version:
            return None, None

        # Additional validation: version should contain at least one dot or be a valid version
        if "." not in plugin_version and not plugin_version.replace(".", "").isdigit():
            return None, None

        return plugin_name, plugin_version

    def _plugin_exists(self, plugin_name: str, plugin_version: str) -> bool:
        """Check if plugin already exists."""
        plugin_dir = self.store_plugin_dir / f"{plugin_name}-{plugin_version}"
        return plugin_dir.exists()

    def _save_archive(self, file: UploadFile, plugin_name: str, plugin_version: str) -> Path:
        """Save the uploaded archive to the archived directory."""
        archive_path = self.store_archived_dir / f"{plugin_name}-{plugin_version}.zip"

        with open(archive_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return archive_path

    def _extract_plugin(self, archive_path: Path, plugin_name: str, plugin_version: str) -> Path:
        """Extract the plugin from the archive."""
        plugin_dir = self.store_plugin_dir / f"{plugin_name}-{plugin_version}"

        # Remove existing directory if it exists
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)

        # Extract zip file
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(plugin_dir)

        return plugin_dir

    def _validate_plugin_structure(self, plugin_dir: Path) -> Dict:
        """Validate the plugin directory structure."""
        result = {"valid": False, "errors": [], "warnings": []}

        # Check if directory exists
        if not plugin_dir.exists():
            result["errors"].append("Plugin directory does not exist")
            return result

        # Check for required files
        required_files = ["__init__.py", "plugin.py"]
        for required_file in required_files:
            if not (plugin_dir / required_file).exists():
                result["errors"].append(f"Missing required file: {required_file}")

        # Check for agent directory
        agent_dirs = [d for d in plugin_dir.iterdir() if d.is_dir() and d.name.endswith("_agent")]
        if not agent_dirs:
            result["warnings"].append("No agent directories found (expected *_agent)")

        # Check for tools
        tool_files = list(plugin_dir.rglob("tools.py"))
        if not tool_files:
            result["warnings"].append("No tools.py files found")

        # If no errors, mark as valid
        if not result["errors"]:
            result["valid"] = True

        return result

    def _install_plugin(self, plugin_dir: Path, plugin_name: str, plugin_version: str) -> Dict:
        """Install the plugin by adding it to the plugin directories."""
        result = {"success": False, "errors": []}

        try:
            # Add the plugin directory to the plugin manager's directories
            plugin_dir_str = str(plugin_dir)
            if plugin_dir_str not in settings.plugins_dir:
                # Update settings to include the new plugin directory
                # Note: This is a temporary solution. In production, you might want
                # to persist this configuration or use a different approach
                settings.plugins_dir.append(plugin_dir_str)

            result["success"] = True
            result["plugin_dir"] = plugin_dir_str

        except Exception as e:
            result["errors"].append(f"Failed to install plugin: {str(e)}")

        return result

    def _cleanup_failed_upload(self, plugin_dir: Path, archive_path: Path):
        """Clean up files from a failed upload."""
        try:
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
            if archive_path.exists():
                archive_path.unlink()
        except Exception as e:
            # Log cleanup errors but don't fail the upload
            print(f"Warning: Failed to cleanup failed upload: {e}")

    def list_uploaded_plugins(self) -> List[Dict]:
        """List all uploaded plugins."""
        plugins = []

        for plugin_dir in self.store_plugin_dir.iterdir():
            if plugin_dir.is_dir():
                plugin_name, plugin_version = self._parse_plugin_filename(plugin_dir.name)
                if plugin_name and plugin_version:
                    plugins.append(
                        {
                            "name": plugin_name,
                            "version": plugin_version,
                            "directory": str(plugin_dir),
                            "archive": str(self.store_archived_dir / f"{plugin_name}-{plugin_version}.zip"),
                        }
                    )

        return plugins

    def delete_plugin(self, plugin_name: str, plugin_version: str) -> bool:
        """Delete an uploaded plugin."""
        try:
            plugin_dir = self.store_plugin_dir / f"{plugin_name}-{plugin_version}"
            archive_path = self.store_archived_dir / f"{plugin_name}-{plugin_version}.zip"

            # Remove plugin directory
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)

            # Remove archive
            if archive_path.exists():
                archive_path.unlink()

            # Reload plugin manager
            self.plugin_manager.reload_plugins()

            return True
        except Exception as e:
            print(f"Error deleting plugin {plugin_name}-{plugin_version}: {e}")
            return False
