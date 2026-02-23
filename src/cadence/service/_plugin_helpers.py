"""Pure helper functions for plugin catalog operations."""

import importlib.util
import io
import logging
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def build_default_settings_lookup(
    system_repo_rows: List[Any], org_repo_rows: List[Any]
) -> Dict[str, Dict[str, Any]]:
    """Build plugin_id → default_settings lookup; org settings override system settings."""
    defaults: Dict[str, Dict[str, Any]] = {}
    for row in system_repo_rows:
        defaults[row.pid] = dict(row.default_settings or {})
    for row in org_repo_rows:
        defaults[row.pid] = dict(row.default_settings or {})
    return defaults


def build_plugin_names_lookup(
    system_repo_rows: List[Any], org_repo_rows: List[Any]
) -> Dict[str, str]:
    """Build plugin_id → name lookup; org plugin names override system plugin names."""
    names: Dict[str, str] = {}
    for row in system_repo_rows:
        names[row.pid] = row.name
    for row in org_repo_rows:
        names[row.pid] = row.name
    return names


def extract_default_settings_from_schema(
    plugin_class: Any, plugin_id: str
) -> Dict[str, Any]:
    """Extract default_settings from the SDK plugin_settings decorator."""
    default_settings: Dict[str, Any] = {}
    try:
        from cadence_sdk.decorators.settings_decorators import (
            get_plugin_settings_schema as sdk_get_schema,
        )

        schema = sdk_get_schema(plugin_class)
        for schema_field in schema:
            key = schema_field.get("key")
            if key:
                default_settings[key] = schema_field.get("default")
    except Exception as e:
        logger.warning(f"Could not extract default_settings for {plugin_id}: {e}")
    return default_settings


def validate_plugin_dependencies(dependencies: List[str]) -> None:
    """Install plugin dependencies in an isolated temp directory to verify they are valid.

    Uses pip install --target=<tmpdir> in a subprocess so the main process
    is never affected. Temp directory is cleaned up automatically.

    Args:
        dependencies: List of pip dependency specs (e.g. ["requests>=2.28"])

    Raises:
        ValueError: If any dependency fails to install (not found, conflict, timeout)
    """
    if not dependencies:
        return

    logger.info(f"Validating plugin dependencies: {dependencies}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--target", tmp_dir, "--quiet"]
                + dependencies,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise ValueError(
                "Plugin dependency installation timed out after 120 seconds. "
                f"Dependencies: {dependencies}"
            )

        if result.returncode != 0:
            error_output = (result.stderr or result.stdout or "").strip()
            logger.warning(
                f"Plugin dependency validation failed for {dependencies}: {error_output}"
            )
            raise ValueError(f"Plugin dependency installation failed:\n{error_output}")

    logger.info(f"Plugin dependencies validated successfully: {dependencies}")


def extract_full_plugin_metadata(zip_bytes: bytes) -> Dict[str, Any]:
    """Extract full plugin metadata from a zip archive.

    Loads plugin.py, instantiates the BasePlugin subclass, extracts
    metadata and default_settings via the SDK.

    Args:
        zip_bytes: Raw zip archive bytes

    Returns:
        Dict with pid, version, name, description, capabilities,
        agent_type, stateless, default_settings, tag

    Raises:
        ValueError: If zip is invalid or metadata cannot be extracted
    """
    try:
        zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid zip archive: {e}") from e

    plugin_file_paths = [
        name for name in zip_file.namelist() if name.endswith("plugin.py")
    ]
    if not plugin_file_paths:
        raise ValueError("No plugin.py found in zip archive")

    plugin_file_path = plugin_file_paths[0]

    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_directory_path = Path(tmp_dir)
        zip_file.extractall(temp_directory_path)
        zip_file.close()

        plugin_file = temp_directory_path / plugin_file_path
        inspection_module_name = "_cadence_upload_inspect"

        module_spec = importlib.util.spec_from_file_location(
            inspection_module_name, plugin_file
        )
        if module_spec is None or module_spec.loader is None:
            raise ValueError("Cannot load plugin.py from zip")

        module = importlib.util.module_from_spec(module_spec)
        sys.path.insert(0, str(plugin_file.parent))
        try:
            module_spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(plugin_file.parent))

        from cadence_sdk.base import BasePlugin

        plugin_class = None
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if (
                isinstance(attribute, type)
                and issubclass(attribute, BasePlugin)
                and attribute is not BasePlugin
            ):
                plugin_class = attribute
                break

        if plugin_class is None:
            raise ValueError("No BasePlugin subclass found in plugin.py")

        meta = plugin_class.get_metadata()
        validate_plugin_dependencies(list(meta.dependencies or []))
        default_settings = extract_default_settings_from_schema(plugin_class, meta.pid)

        return {
            "pid": meta.pid,
            "version": meta.version,
            "name": meta.name,
            "description": getattr(meta, "description", None),
            "capabilities": list(meta.capabilities or []),
            "agent_type": getattr(meta, "agent_type", "specialized"),
            "stateless": getattr(meta, "stateless", True),
            "default_settings": default_settings,
            "tag": getattr(meta, "tag", None),
        }


def validate_plugin_id_matches_domain(plugin_id: str, domain: str) -> None:
    """Ensure the plugin ID matches the org domain in reverse-domain notation.

    For domain 'acme.com' the plugin_id must equal 'com.acme' or start with 'com.acme.'
    (e.g. 'com.acme.search', 'com.acme.tools.v2').

    Args:
        plugin_id: Reverse-domain plugin identifier extracted from the package
        domain: Organization domain (e.g. 'acme.com')

    Raises:
        ValueError: If the plugin_id does not match the expected reverse-domain prefix
    """
    reversed_domain = ".".join(reversed(domain.lower().strip().split(".")))
    plugin_id_lower = plugin_id.lower().strip()
    if plugin_id_lower != reversed_domain and not plugin_id_lower.startswith(
        reversed_domain + "."
    ):
        raise ValueError(
            f"Plugin pid '{plugin_id}' does not match organization domain '{domain}'. "
            f"The pid must start with '{reversed_domain}' "
            f"(e.g. '{reversed_domain}.my-plugin')."
        )


def serialize_system_plugin(plugin: Any) -> Dict[str, Any]:
    """Convert SystemPlugin ORM object to API response dict."""
    return {
        "id": str(plugin.id),
        "pid": plugin.pid,
        "version": plugin.version,
        "name": plugin.name,
        "description": plugin.description or "",
        "tag": plugin.tag,
        "is_latest": plugin.is_latest,
        "s3_path": plugin.s3_path,
        "default_settings": plugin.default_settings or {},
        "capabilities": plugin.capabilities or [],
        "agent_type": plugin.agent_type,
        "stateless": plugin.stateless,
        "source": "system",
    }


def serialize_org_plugin(plugin: Any) -> Dict[str, Any]:
    """Convert OrgPlugin ORM object to API response dict."""
    return {
        "id": str(plugin.id),
        "pid": plugin.pid,
        "version": plugin.version,
        "name": plugin.name,
        "description": plugin.description or "",
        "tag": plugin.tag,
        "is_latest": plugin.is_latest,
        "s3_path": plugin.s3_path,
        "default_settings": plugin.default_settings or {},
        "capabilities": plugin.capabilities or [],
        "agent_type": plugin.agent_type,
        "stateless": plugin.stateless,
        "source": "org",
    }
