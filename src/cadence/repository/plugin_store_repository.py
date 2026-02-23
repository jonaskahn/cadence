"""Two-level plugin storage: local filesystem (cache) + S3/MinIO (source of truth).

Storage layout:
  S3 bucket (cadence-plugins):
    system/{pid}/{version}/plugin.zip
    tenants/{org_id}/{pid}/{version}/plugin.zip

  Local filesystem:
    {system_plugins_dir}/{pid}/{version}/    ← extracted system plugin
    {tenant_plugins_root}/{org_id}/{pid}/{version}/  ← extracted tenant plugin
"""

import io
import logging
import zipfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class PluginStoreRepository:
    """Two-level plugin storage manager.

    S3/MinIO is the source of truth. The local filesystem is a cache.
    When plugin_store.s3_enabled is False, only local filesystem is used.

    Attributes:
        s3_client: S3Client instance (None if S3 disabled)
        tenant_plugins_root: Root directory for tenant plugin cache
        system_plugins_dir: Directory for system plugin cache
        s3_enabled: Whether S3 backend is active
    """

    def __init__(
        self,
        tenant_plugins_root: str,
        system_plugins_dir: str,
        s3_client=None,
    ):
        """Initialize plugin store.

        Args:
            tenant_plugins_root: Root directory for tenant plugins
            system_plugins_dir: Directory for system plugins
            s3_client: Optional S3Client (S3 disabled if None)
        """
        self.s3_client = s3_client
        self.s3_enabled = s3_client is not None
        self.tenant_plugins_root = Path(tenant_plugins_root)
        self.system_plugins_dir = Path(system_plugins_dir)

    @staticmethod
    def s3_key(pid: str, version: str, org_id: Optional[str] = None) -> str:
        """Build S3 object key for a plugin zip.

        Args:
            pid: Plugin identifier
            version: Plugin version string
            org_id: Organization ID (None for system plugins)

        Returns:
            S3 key string
        """
        if org_id:
            return f"tenants/{org_id}/{pid}/{version}/plugin.zip"
        return f"system/{pid}/{version}/plugin.zip"

    def local_path(self, pid: str, version: str, org_id: Optional[str] = None) -> Path:
        """Build local filesystem path for a plugin directory.

        Args:
            pid: Plugin identifier
            version: Plugin version string
            org_id: Organization ID (None for system plugins)

        Returns:
            Path to the versioned plugin directory
        """
        if org_id:
            return self.tenant_plugins_root / org_id / pid / version
        return self.system_plugins_dir / pid / version

    async def upload(
        self,
        pid: str,
        version: str,
        zip_bytes: bytes,
        org_id: Optional[str] = None,
    ) -> Path:
        """Upload plugin zip to S3 and extract to local cache.

        Args:
            pid: Plugin identifier
            version: Plugin version string
            zip_bytes: Raw bytes of plugin zip archive
            org_id: Organization ID (None for system plugins)

        Returns:
            Local path where plugin was extracted

        Raises:
            ValueError: If zip_bytes is not a valid zip archive
        """
        local_dir = self.local_path(pid, version, org_id)

        if self.s3_enabled:
            key = self.s3_key(pid, version, org_id)
            await self.s3_client.upload_file(key, zip_bytes)
            logger.info(f"Uploaded plugin to S3: {key}")

        _extract_zip(zip_bytes, local_dir)
        logger.info(f"Extracted plugin to local cache: {local_dir}")

        return local_dir

    async def ensure_local(
        self,
        pid: str,
        version: str,
        org_id: Optional[str] = None,
    ) -> Path:
        """Ensure plugin is available locally, downloading from S3 if needed.

        If the local directory exists, returns it immediately (cache hit).
        Otherwise, downloads from S3 and extracts to local cache.

        Args:
            pid: Plugin identifier
            version: Plugin version string
            org_id: Organization ID (None for system plugins)

        Returns:
            Local path to the plugin directory

        Raises:
            FileNotFoundError: If plugin not in S3 and not in local cache
        """
        local_dir = self.local_path(pid, version, org_id)

        if local_dir.exists() and any(local_dir.iterdir()):
            logger.debug(f"Plugin cache hit: {local_dir}")
            return local_dir

        if not self.s3_enabled:
            if not local_dir.exists():
                raise FileNotFoundError(
                    f"Plugin '{pid}' version '{version}' not found locally "
                    f"and S3 is disabled."
                )
            return local_dir

        key = self.s3_key(pid, version, org_id)
        logger.info(f"Cache miss — downloading from S3: {key}")
        zip_bytes = await self.s3_client.download_file(key)

        _extract_zip(zip_bytes, local_dir)
        logger.info(f"Extracted plugin from S3 to: {local_dir}")

        return local_dir

    async def list_versions(self, pid: str, org_id: Optional[str] = None) -> List[str]:
        """List all versions of a plugin available in S3.

        Args:
            pid: Plugin identifier
            org_id: Organization ID (None for system plugins)

        Returns:
            List of version strings (may be empty if S3 disabled or plugin absent)
        """
        if not self.s3_enabled:
            return _list_local_versions(self.local_path(pid, "", org_id).parent)

        if org_id:
            prefix = f"tenants/{org_id}/{pid}/"
        else:
            prefix = f"system/{pid}/"

        keys = await self.s3_client.list_objects(prefix)
        versions = set()
        for key in keys:
            parts = key.split("/")
            version_idx = len(prefix.split("/")) - 1
            if len(parts) > version_idx:
                versions.add(parts[version_idx])

        return sorted(versions)

    async def version_exists_locally(
        self, pid: str, version: str, org_id: Optional[str] = None
    ) -> bool:
        """Check if a plugin version exists in local cache.

        Args:
            pid: Plugin identifier
            version: Plugin version string
            org_id: Organization ID (None for system plugins)

        Returns:
            True if local directory exists and is non-empty
        """
        local_dir = self.local_path(pid, version, org_id)
        return local_dir.exists() and any(local_dir.iterdir())

    async def version_exists_in_s3(
        self, pid: str, version: str, org_id: Optional[str] = None
    ) -> bool:
        """Check if a plugin version exists in S3.

        Args:
            pid: Plugin identifier
            version: Plugin version string
            org_id: Organization ID (None for system plugins)

        Returns:
            True if object exists in S3; always False if S3 disabled
        """
        if not self.s3_enabled:
            return False
        key = self.s3_key(pid, version, org_id)
        return await self.s3_client.object_exists(key)


def _detect_zip_prefix(infos) -> Optional[str]:
    """Return single top-level directory prefix if all entries share one, else None."""
    if not infos:
        return None
    top_names = {info.filename.split("/")[0] for info in infos if info.filename}
    if len(top_names) != 1:
        return None
    sole = top_names.pop()
    prefix = sole + "/"
    if all(
        info.filename == prefix or info.filename.startswith(prefix) for info in infos
    ):
        return prefix
    return None


def _extract_zip(zip_bytes: bytes, target_dir: Path) -> None:
    """Extract zip archive bytes to target directory, stripping single top-level wrapper.

    If all entries in the zip share a single top-level directory (e.g. the zip
    was created with ``zip -r plugin.zip template_plugin/``), that wrapper
    directory is stripped so that plugin.py lands directly in target_dir.

    Args:
        zip_bytes: Raw zip archive bytes
        target_dir: Directory to extract into (created if absent)

    Raises:
        ValueError: If zip_bytes is not a valid zip file
    """
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            infos = zf.infolist()
            prefix = _detect_zip_prefix(infos)

            if prefix:
                for info in infos:
                    relative_path = info.filename[len(prefix) :]
                    if not relative_path:
                        continue
                    out_path = target_dir / relative_path
                    if info.is_dir():
                        out_path.mkdir(parents=True, exist_ok=True)
                    else:
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(info) as source_file:
                            out_path.write_bytes(source_file.read())
            else:
                zf.extractall(target_dir)
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid zip archive: {e}") from e


def _list_local_versions(pid_dir: Path) -> List[str]:
    """List version subdirectories under a pid directory.

    Args:
        pid_dir: Directory containing version subdirectories

    Returns:
        Sorted list of version directory names
    """
    if not pid_dir.exists() or not pid_dir.is_dir():
        return []
    return sorted(
        item.name
        for item in pid_dir.iterdir()
        if item.is_dir() and not item.name.startswith(".")
    )
