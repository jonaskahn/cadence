"""Manage plugin uploads, validation, installs and lifecycle.

Stable package layout: storage_root/uploaded/<sanitized_name>/ with metadata.json.
Supports version gating, atomic upgrades with rollback, and archival of previous versions.
"""

import json
import logging
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

from ...config.settings import settings
from .sdk_manager import SDKPluginManager

try:
    from packaging.version import parse as parse_version
except Exception:  # pragma: no cover - fallback if packaging missing
    parse_version = None


class PluginUploadResult(BaseModel):
    """Result of a plugin upload operation."""

    success: bool
    plugin_name: Optional[str] = None
    plugin_version: Optional[str] = None
    message: str
    details: Optional[Dict] = None


class PluginUploadManager:
    """Manage plugin uploads, validation, installation, and listing."""

    def __init__(self, plugin_manager: SDKPluginManager):
        self.plugin_manager = plugin_manager
        self.logger = logging.getLogger(__name__)
        self.storage_root = Path(settings.storage_root)
        self.store_plugin_dir = self.storage_root / "uploaded"
        self.store_archived_dir = self.storage_root / "archived"
        self._staging_base = self.storage_root / "staging"
        self._backup_base = self.storage_root / "backup"

        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.store_plugin_dir.mkdir(parents=True, exist_ok=True)
        self.store_archived_dir.mkdir(parents=True, exist_ok=True)
        self._staging_base.mkdir(parents=True, exist_ok=True)
        self._backup_base.mkdir(parents=True, exist_ok=True)

    def upload_plugin(self, file: UploadFile, force_overwrite: bool = False) -> PluginUploadResult:
        """Upload a plugin ZIP, validate, install atomically, archive previous."""
        try:
            if not self._validate_upload_file(file):
                return PluginUploadResult(success=False, message="Invalid file format. Only ZIP files are supported.")

            plugin_name, plugin_version = self._parse_plugin_filename(file.filename)
            if not plugin_name or not plugin_version:
                return PluginUploadResult(success=False, message="Invalid filename format. Expected: name-version.zip")

            sanitized_name = self._get_sanitized_name(plugin_name)
            self.logger.debug(f"upload start name={plugin_name} version={plugin_version} sanitized={sanitized_name}")

            archive_path = self._save_archive(file, plugin_name, plugin_version)
            self.logger.debug(f"saved archive at {archive_path}")

            container_dir = self.store_plugin_dir / sanitized_name
            metadata_path = container_dir / "metadata.json"
            existing_metadata = self._read_metadata(metadata_path)
            self.logger.debug(
                f"existing container exists={container_dir.exists()} metadata_version={existing_metadata.get('version') if existing_metadata else None}"
            )

            if not force_overwrite and existing_metadata and existing_metadata.get("version"):
                if not self._is_newer_version(plugin_version, str(existing_metadata.get("version"))):
                    return PluginUploadResult(
                        success=False,
                        plugin_name=plugin_name,
                        plugin_version=plugin_version,
                        message=(
                            f"Incoming version {plugin_version} is not newer than installed "
                            f"{existing_metadata.get('version')}. Use force_overwrite=True to replace."
                        ),
                    )

            staging_dir = self._extract_to_staging(archive_path)
            self.logger.debug(f"extracted to staging {staging_dir}")
            try:
                package_dir = self._ensure_package_layout(staging_dir, sanitized_name)
                self.logger.debug(f"normalized package_dir={package_dir}")
            except Exception as e:
                shutil.rmtree(staging_dir, ignore_errors=True)
                return PluginUploadResult(
                    success=False,
                    plugin_name=plugin_name,
                    plugin_version=plugin_version,
                    message=f"Failed to prepare package layout: {e}",
                )

            validation_result = self._validate_package_dir(package_dir)
            self.logger.debug(
                f"validation result valid={validation_result.get('valid')} errors={validation_result.get('errors')} warnings={validation_result.get('warnings')}"
            )
            if not validation_result["valid"]:
                shutil.rmtree(staging_dir, ignore_errors=True)
                return PluginUploadResult(
                    success=False,
                    plugin_name=plugin_name,
                    plugin_version=plugin_version,
                    message="Plugin validation failed",
                    details=validation_result,
                )

            backup_root_dir = self._make_temp_dir(self._backup_base, prefix="backup_")
            backup_dir = backup_root_dir / sanitized_name
            try:
                if container_dir.exists():
                    self.logger.debug(f"moving existing container {container_dir} to backup {backup_dir}")
                    shutil.move(str(container_dir), str(backup_dir))
                else:
                    self.logger.debug("no existing container to backup")

                move_src = package_dir
                if move_src.name != sanitized_name:
                    new_container = staging_dir / sanitized_name
                    new_container.mkdir(parents=True, exist_ok=True)
                    for item in list(package_dir.iterdir()):
                        if item.resolve() == new_container.resolve():
                            continue
                        shutil.move(str(item), str(new_container / item.name))
                    move_src = new_container

                self.logger.debug(f"moving source {move_src} to container {container_dir}")
                shutil.move(str(move_src), str(container_dir))

                now_iso = datetime.now(timezone.utc).isoformat()
                new_metadata: Dict[str, Any] = existing_metadata or {}
                if not new_metadata.get("created_date"):
                    new_metadata["created_date"] = now_iso
                new_metadata["name"] = plugin_name
                new_metadata["sanitized_name"] = sanitized_name
                new_metadata["version"] = plugin_version
                new_metadata["updated_date"] = now_iso
                new_metadata["source_archive"] = str(archive_path)

                history = list(new_metadata.get("history") or [])
                if existing_metadata and existing_metadata.get("version"):
                    old_version = str(existing_metadata.get("version"))
                    if backup_dir.exists():
                        archive_dest = self._build_archive_destination(plugin_name, old_version)
                        try:
                            self._archive_directory(backup_dir, archive_dest)
                            history.append(
                                {
                                    "version": old_version,
                                    "archived_at": now_iso,
                                    "archive_path": str(archive_dest),
                                }
                            )
                        finally:
                            shutil.rmtree(backup_root_dir, ignore_errors=True)
                else:
                    shutil.rmtree(backup_root_dir, ignore_errors=True)

                new_metadata["history"] = history
                self.logger.debug(f"writing metadata to {metadata_path}")
                self._write_metadata(metadata_path, new_metadata)

            except Exception as e:
                try:
                    if container_dir.exists():
                        shutil.rmtree(container_dir, ignore_errors=True)
                    if backup_dir.exists():
                        self.logger.debug(f"rollback: restoring backup from {backup_dir} to {container_dir}")
                        shutil.move(str(backup_dir), str(container_dir))
                finally:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    shutil.rmtree(backup_root_dir, ignore_errors=True)
                return PluginUploadResult(
                    success=False,
                    plugin_name=plugin_name,
                    plugin_version=plugin_version,
                    message=f"Plugin installation failed: {e}",
                )

            self.logger.debug(f"cleanup staging {staging_dir}")
            shutil.rmtree(staging_dir, ignore_errors=True)

            self.logger.debug("reloading plugin manager")
            self.plugin_manager.reload_plugins()

            return PluginUploadResult(
                success=True,
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                message=f"Plugin {plugin_name}-{plugin_version} uploaded and installed successfully",
                details={
                    "archive_path": str(archive_path),
                    "plugin_dir": str(container_dir),
                    "validation": validation_result,
                },
            )

        except Exception as e:
            return PluginUploadResult(success=False, message=f"Upload failed: {str(e)}")

    @staticmethod
    def _validate_upload_file(file: UploadFile) -> bool:
        """Validate basic file constraints for a ZIP."""
        if not file.filename:
            return False

        # Check file extension
        if not file.filename.lower().endswith(".zip"):
            return False

        # Check file size (max 50MB)
        if hasattr(file, "size") and file.size and file.size > 50 * 1024 * 1024:
            return False

        return True

    @staticmethod
    def _parse_plugin_filename(filename: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse name and version from name-version.zip."""
        if not filename or not filename.endswith(".zip"):
            return None, None

        base_name = filename[:-4]
        if "-" not in base_name:
            return None, None
        last_dash_index = base_name.rfind("-")
        if last_dash_index == 0:  # Only dash at beginning
            return None, None

        plugin_name = base_name[:last_dash_index]
        plugin_version = base_name[last_dash_index + 1 :]
        if not plugin_name or not plugin_version:
            return None, None
        if "." not in plugin_version and not plugin_version.replace(".", "").isdigit():
            return None, None

        return plugin_name, plugin_version

    @staticmethod
    def _get_sanitized_name(plugin_name: str) -> str:
        """Return valid Python package identifier for the plugin name."""
        return plugin_name.replace("-", "_")

    # Note: previous _plugin_exists helper removed as unused

    def _save_archive(self, file: UploadFile, plugin_name: str, plugin_version: str) -> Path:
        """Save uploaded archive under storage/archived and return its path."""
        archive_path = self.store_archived_dir / f"{plugin_name}-{plugin_version}.zip"

        with open(archive_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return archive_path

    def _extract_to_staging(self, archive_path: Path) -> Path:
        """Extract archive into a temporary staging directory and return it."""
        staging_dir = self._make_temp_dir(self._staging_base, prefix="stage_")
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(staging_dir)
        self.logger.debug(f"extracted entries: {[p.name for p in staging_dir.iterdir()]}")
        return staging_dir

    @staticmethod
    def _make_temp_dir(base: Path, prefix: str = "tmp_") -> Path:
        base.mkdir(parents=True, exist_ok=True)
        # ensure unique directory
        unique = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        path = base / f"{prefix}{unique}"
        path.mkdir(parents=True, exist_ok=False)
        return path

    @staticmethod
    def _validate_package_dir(package_dir: Path) -> Dict:
        """Validate that package_dir is importable and shaped as a plugin."""
        result = {"valid": False, "errors": [], "warnings": []}

        if not package_dir.exists():
            result["errors"].append("Plugin package directory does not exist")
            return result

        required_files = ["__init__.py", "plugin.py"]
        for required_file in required_files:
            if not (package_dir / required_file).exists():
                result["errors"].append(f"Missing required file: {required_file}")

        # Optional checks
        agent_dirs = [d for d in package_dir.iterdir() if d.is_dir() and d.name.endswith("_agent")]
        if not agent_dirs:
            result["warnings"].append("No agent directories found (expected *_agent)")

        tool_files = list(package_dir.rglob("tools.py"))
        if not tool_files:
            result["warnings"].append("No tools.py files found")

        if not result["errors"]:
            result["valid"] = True
        return result

    def _find_primary_package_dir(self, staging_root: Path) -> Optional[Path]:
        """Pick top-level package root: single dir or root if plugin.py exists."""
        try:
            entries = [p for p in staging_root.iterdir() if p.is_dir()]
        except Exception:
            entries = []
        if len(entries) == 1 and not any(p.is_file() for p in staging_root.iterdir()):
            self.logger.debug(f"primary candidate dir={entries[0]}")
            return entries[0]
        if (staging_root / "plugin.py").exists():
            self.logger.debug("primary candidate is staging root")
            return staging_root
        return None

    def _ensure_package_layout(self, staging_root: Path, sanitized_name: str) -> Path:
        """Normalize layout under an importable package directory named sanitized_name."""
        candidate = self._find_primary_package_dir(staging_root)
        if candidate is None:
            # Multiple items or files at root: consolidate into sanitized_name
            package_dir = staging_root / sanitized_name
            if not package_dir.exists():
                package_dir.mkdir(parents=True, exist_ok=False)
            for item in list(staging_root.iterdir()):
                if item.resolve() == package_dir.resolve():
                    continue
                shutil.move(str(item), str(package_dir / item.name))
        else:
            # If candidate is the staging root itself, don't attempt to move it into a child
            if candidate.resolve() == staging_root.resolve():
                package_dir = candidate
            elif candidate.name == sanitized_name:
                package_dir = candidate
            else:
                # Prefer renaming the directory if target doesn't exist
                target_dir = staging_root / sanitized_name
                if not target_dir.exists():
                    shutil.move(str(candidate), str(target_dir))
                    package_dir = target_dir
                else:
                    # Target exists: move contents and remove candidate
                    for item in list(candidate.iterdir()):
                        shutil.move(str(item), str(target_dir / item.name))
                    shutil.rmtree(candidate, ignore_errors=True)
                    package_dir = target_dir

        init_file = package_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("")
        self.logger.debug(f"ensured __init__ at {init_file}")

        return package_dir

    def _is_newer_version(self, new_version: str, current_version: str) -> bool:
        """True if new_version is strictly greater than current_version (PEP 440)."""
        if parse_version is None:
            # Fallback: naive string compare; consider different => newer
            return str(new_version) != str(current_version)
        try:
            return parse_version(new_version) > parse_version(current_version)
        except Exception:
            # If parsing fails, only allow when versions differ
            return str(new_version) != str(current_version)

    def _read_metadata(self, metadata_path: Path) -> Optional[Dict[str, Any]]:
        try:
            if metadata_path.exists():
                with open(metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            return None
        return None

    def _write_metadata(self, metadata_path: Path, data: Dict[str, Any]) -> None:
        tmp_path = metadata_path.with_suffix(".tmp")
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, metadata_path)

    def _build_archive_destination(self, plugin_name: str, version: str) -> Path:
        base = self.store_archived_dir / f"{plugin_name}-{version}.zip"
        if not base.exists():
            return base
        # add timestamp to avoid collisions
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return self.store_archived_dir / f"{plugin_name}-{version}-{ts}.zip"

    def _archive_directory(self, src_dir: Path, archive_dest_zip: Path) -> None:
        archive_dest_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(src_dir):
                for file_name in files:
                    file_path = Path(root) / file_name
                    # store relative to src_dir to keep clean structure inside zip
                    arcname = str(file_path.relative_to(src_dir.parent))
                    zf.write(file_path, arcname)

    @staticmethod
    def _install_plugin(plugin_dir: Path, plugin_name: str, plugin_version: str) -> Dict:
        """Deprecated: Installation is implicit via stable directory; kept for compatibility."""
        result = {"success": True, "plugin_dir": str(plugin_dir)}
        return result

    @staticmethod
    def _cleanup_failed_upload(plugin_dir: Path, archive_path: Path):
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
        """List all uploaded plugins from stable directories using metadata."""
        plugins: List[Dict[str, Any]] = []
        if not self.store_plugin_dir.exists():
            return plugins

        for entry in self.store_plugin_dir.iterdir():
            try:
                if not entry.is_dir():
                    continue
                metadata = self._read_metadata(entry / "metadata.json") or {}
                name = metadata.get("name") or entry.name
                version = metadata.get("version") or ""
                archive_guess = self.store_archived_dir / f"{name}-{version}.zip" if version else None
                plugins.append(
                    {
                        "name": name,
                        "version": version,
                        "directory": str(entry),
                        "archive": str(archive_guess) if archive_guess else None,
                    }
                )
            except Exception as e:
                # Skip problematic entries but continue listing others
                try:
                    print(f"Warning: failed to list plugin at {entry}: {e}")
                except Exception:
                    pass

        return plugins

    def delete_plugin(self, plugin_name: str, plugin_version: str) -> bool:
        """Delete an uploaded plugin by name (version is optional and used to remove the matching archive)."""
        try:
            sanitized_name = self._get_sanitized_name(plugin_name)
            plugin_dir = self.store_plugin_dir / sanitized_name
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)

            if plugin_version:
                archive_path = self.store_archived_dir / f"{plugin_name}-{plugin_version}.zip"
                if archive_path.exists():
                    archive_path.unlink()

            self.plugin_manager.reload_plugins()
            return True
        except Exception as e:
            print(f"Error deleting plugin {plugin_name}: {e}")
            return False
