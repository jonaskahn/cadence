"""Unit tests for PluginService.

Verifies upload flow (metadata extraction, S3 store, DB write),
list_available (system + org combined), get_settings_schema, and
build_initial_plugin_settings.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cadence.service.plugin_service import (
    PluginService,
    _org_plugin_to_dict,
    _system_plugin_to_dict,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def plugin_store() -> MagicMock:
    store = MagicMock()
    store.upload = AsyncMock(return_value=None)
    store.ensure_local = AsyncMock(return_value=None)
    return store


@pytest.fixture
def svc(
    system_plugin_repo: MagicMock,
    org_plugin_catalog_repo: MagicMock,
    plugin_store: MagicMock,
) -> PluginService:
    return PluginService(
        system_plugin_repo=system_plugin_repo,
        org_plugin_repo=org_plugin_catalog_repo,
        plugin_store=plugin_store,
    )


@pytest.fixture
def svc_no_store(
    system_plugin_repo: MagicMock,
    org_plugin_catalog_repo: MagicMock,
) -> PluginService:
    return PluginService(
        system_plugin_repo=system_plugin_repo,
        org_plugin_repo=org_plugin_catalog_repo,
        plugin_store=None,
    )


def _make_fake_zip_bytes() -> bytes:
    """Return bytes that look like a valid zip to mock extraction."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("plugin.py", "# fake plugin")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# upload_system_plugin
# ---------------------------------------------------------------------------


class TestUploadSystemPlugin:
    """Tests for PluginService.upload_system_plugin."""

    async def test_calls_plugin_store_upload(
        self, svc: PluginService, plugin_store: MagicMock
    ) -> None:
        """upload_system_plugin uploads zip to S3 via plugin_store."""
        fake_meta = {
            "pid": "com.example.search",
            "version": "1.0.0",
            "name": "Search",
            "description": "Search plugin",
            "capabilities": ["search"],
            "agent_type": "specialized",
            "stateless": True,
            "default_settings": {"api_key": None},
            "tag": None,
        }
        with patch(
            "cadence.service.plugin_service._extract_full_plugin_metadata",
            return_value=fake_meta,
        ):
            await svc.upload_system_plugin(b"zipdata", caller_id="user_1")

        plugin_store.upload.assert_awaited_once_with(
            pid="com.example.search",
            version="1.0.0",
            zip_bytes=b"zipdata",
            org_id=None,
        )

    async def test_calls_repo_upload_with_correct_args(
        self, svc: PluginService, system_plugin_repo: MagicMock
    ) -> None:
        """upload_system_plugin writes correct row to system_plugin_repo."""
        fake_meta = {
            "pid": "com.example.search",
            "version": "1.0.0",
            "name": "Search",
            "description": "Desc",
            "capabilities": [],
            "agent_type": "specialized",
            "stateless": True,
            "default_settings": {"api_key": None},
            "tag": "search",
        }
        with patch(
            "cadence.service.plugin_service._extract_full_plugin_metadata",
            return_value=fake_meta,
        ):
            await svc.upload_system_plugin(b"zipdata", caller_id="user_1")

        system_plugin_repo.upload.assert_awaited_once()
        call_kwargs = system_plugin_repo.upload.call_args.kwargs
        assert call_kwargs["pid"] == "com.example.search"
        assert call_kwargs["version"] == "1.0.0"
        assert (
            call_kwargs["s3_path"]
            == "plugins/system/com.example.search/1.0.0/plugin.zip"
        )
        assert call_kwargs["caller_id"] == "user_1"

    async def test_returns_plugin_row(
        self, svc: PluginService, system_plugin_repo: MagicMock
    ) -> None:
        """upload_system_plugin returns the ORM row from the repository."""
        fake_meta = {
            "pid": "com.example.x",
            "version": "0.1.0",
            "name": "X",
            "description": None,
            "capabilities": [],
            "agent_type": "specialized",
            "stateless": True,
            "default_settings": {},
            "tag": None,
        }
        with patch(
            "cadence.service.plugin_service._extract_full_plugin_metadata",
            return_value=fake_meta,
        ):
            result = await svc.upload_system_plugin(b"data")

        assert result is system_plugin_repo.upload.return_value

    async def test_skips_store_when_no_plugin_store(
        self, svc_no_store: PluginService, system_plugin_repo: MagicMock
    ) -> None:
        """upload_system_plugin still writes DB row even when plugin_store is None."""
        fake_meta = {
            "pid": "com.example.x",
            "version": "1.0.0",
            "name": "X",
            "description": None,
            "capabilities": [],
            "agent_type": "specialized",
            "stateless": True,
            "default_settings": {},
            "tag": None,
        }
        with patch(
            "cadence.service.plugin_service._extract_full_plugin_metadata",
            return_value=fake_meta,
        ):
            await svc_no_store.upload_system_plugin(b"data")

        system_plugin_repo.upload.assert_awaited_once()


# ---------------------------------------------------------------------------
# upload_org_plugin
# ---------------------------------------------------------------------------


class TestUploadOrgPlugin:
    """Tests for PluginService.upload_org_plugin."""

    async def test_calls_plugin_store_with_org_id(
        self, svc: PluginService, plugin_store: MagicMock
    ) -> None:
        """upload_org_plugin uploads zip with org_id scoping."""
        fake_meta = {
            "pid": "com.example.custom",
            "version": "2.0.0",
            "name": "Custom",
            "description": None,
            "capabilities": [],
            "agent_type": "specialized",
            "stateless": True,
            "default_settings": {},
            "tag": None,
        }
        with patch(
            "cadence.service.plugin_service._extract_full_plugin_metadata",
            return_value=fake_meta,
        ):
            await svc.upload_org_plugin("org_test", b"zipdata", caller_id="user_2")

        plugin_store.upload.assert_awaited_once_with(
            pid="com.example.custom",
            version="2.0.0",
            zip_bytes=b"zipdata",
            org_id="org_test",
        )

    async def test_calls_org_repo_with_correct_s3_path(
        self, svc: PluginService, org_plugin_catalog_repo: MagicMock
    ) -> None:
        """upload_org_plugin constructs tenant-scoped S3 path."""
        fake_meta = {
            "pid": "com.example.custom",
            "version": "2.0.0",
            "name": "Custom",
            "description": None,
            "capabilities": [],
            "agent_type": "specialized",
            "stateless": True,
            "default_settings": {},
            "tag": None,
        }
        with patch(
            "cadence.service.plugin_service._extract_full_plugin_metadata",
            return_value=fake_meta,
        ):
            await svc.upload_org_plugin("org_test", b"zipdata")

        call_kwargs = org_plugin_catalog_repo.upload.call_args.kwargs
        assert (
            call_kwargs["s3_path"]
            == "plugins/tenants/org_test/com.example.custom/2.0.0/plugin.zip"
        )
        assert call_kwargs["org_id"] == "org_test"


# ---------------------------------------------------------------------------
# list_available
# ---------------------------------------------------------------------------


class TestListAvailable:
    """Tests for PluginService.list_available."""

    async def test_returns_combined_system_and_org_plugins(
        self,
        svc: PluginService,
        system_plugin_repo: MagicMock,
        org_plugin_catalog_repo: MagicMock,
    ) -> None:
        """list_available combines system and org plugins into one list."""
        result = await svc.list_available("org_test")

        system_plugin_repo.list_all.assert_awaited_once_with(tag=None)
        org_plugin_catalog_repo.list_available.assert_awaited_once_with(
            "org_test", tag=None
        )

        sources = {p["source"] for p in result}
        assert "system" in sources
        assert "org" in sources

    async def test_passes_tag_filter_to_both_repos(
        self,
        svc: PluginService,
        system_plugin_repo: MagicMock,
        org_plugin_catalog_repo: MagicMock,
    ) -> None:
        """list_available forwards tag to both repos."""
        await svc.list_available("org_test", tag="nlp")

        system_plugin_repo.list_all.assert_awaited_once_with(tag="nlp")
        org_plugin_catalog_repo.list_available.assert_awaited_once_with(
            "org_test", tag="nlp"
        )

    async def test_system_plugin_dict_has_source_system(
        self,
        svc: PluginService,
        org_plugin_catalog_repo: MagicMock,
    ) -> None:
        """list_available tags system plugins with source='system'."""
        org_plugin_catalog_repo.list_available.return_value = []

        result = await svc.list_available("org_test")

        assert all(p["source"] == "system" for p in result)

    async def test_org_plugin_dict_has_source_org(
        self,
        svc: PluginService,
        system_plugin_repo: MagicMock,
    ) -> None:
        """list_available tags org plugins with source='org'."""
        system_plugin_repo.list_all.return_value = []

        result = await svc.list_available("org_test")

        assert all(p["source"] == "org" for p in result)

    async def test_result_includes_required_fields(
        self,
        svc: PluginService,
        org_plugin_catalog_repo: MagicMock,
    ) -> None:
        """list_available dicts include all required API response fields."""
        org_plugin_catalog_repo.list_available.return_value = []

        result = await svc.list_available("org_test")

        for p in result:
            for field in (
                "id",
                "pid",
                "version",
                "name",
                "is_latest",
                "source",
                "default_settings",
            ):
                assert field in p, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# build_initial_plugin_settings
# ---------------------------------------------------------------------------


class TestBuildInitialPluginSettings:
    """Tests for PluginService.build_initial_plugin_settings."""

    def _make_plugin_row(
        self, pid: str, defaults: dict, name: str = "Test Plugin"
    ) -> MagicMock:
        row = MagicMock()
        row.pid = pid
        row.name = name
        row.default_settings = defaults
        return row

    def test_keys_by_pid_at_version(self, svc: PluginService) -> None:
        """build_initial_plugin_settings keys result by 'pid@version'."""
        sys_row = self._make_plugin_row("com.example.search", {"api_key": None})

        result = svc.build_initial_plugin_settings(
            active_plugins=["com.example.search@1.0.0"],
            system_repo_rows=[sys_row],
            org_repo_rows=[],
        )

        assert "com.example.search@1.0.0" in result

    def test_entry_has_active_true(self, svc: PluginService) -> None:
        """build_initial_plugin_settings sets active=True on each entry."""
        sys_row = self._make_plugin_row("com.example.search", {})

        result = svc.build_initial_plugin_settings(
            active_plugins=["com.example.search@1.0.0"],
            system_repo_rows=[sys_row],
            org_repo_rows=[],
        )

        assert result["com.example.search@1.0.0"]["active"] is True

    def test_entry_has_version_and_id(self, svc: PluginService) -> None:
        """build_initial_plugin_settings entry includes id and version fields."""
        sys_row = self._make_plugin_row("com.example.search", {})

        result = svc.build_initial_plugin_settings(
            active_plugins=["com.example.search@1.0.0"],
            system_repo_rows=[sys_row],
            org_repo_rows=[],
        )

        entry = result["com.example.search@1.0.0"]
        assert entry["id"] == "com.example.search"
        assert entry["version"] == "1.0.0"

    def test_settings_list_contains_defaults(self, svc: PluginService) -> None:
        """build_initial_plugin_settings populates settings list from catalog defaults."""
        sys_row = self._make_plugin_row(
            "com.example.search", {"api_key": None, "timeout": 30}
        )

        result = svc.build_initial_plugin_settings(
            active_plugins=["com.example.search@1.0.0"],
            system_repo_rows=[sys_row],
            org_repo_rows=[],
        )

        settings_list = result["com.example.search@1.0.0"]["settings"]
        settings_map = {s["key"]: s["value"] for s in settings_list}
        assert settings_map["api_key"] is None
        assert settings_map["timeout"] == 30

    def test_org_overrides_system_defaults(self, svc: PluginService) -> None:
        """build_initial_plugin_settings: org row overrides system row for same pid."""
        sys_row = self._make_plugin_row("com.example.search", {"timeout": 30})
        org_row = self._make_plugin_row("com.example.search", {"timeout": 60})

        result = svc.build_initial_plugin_settings(
            active_plugins=["com.example.search@1.0.0"],
            system_repo_rows=[sys_row],
            org_repo_rows=[org_row],
        )

        settings_list = result["com.example.search@1.0.0"]["settings"]
        settings_map = {s["key"]: s["value"] for s in settings_list}
        assert settings_map["timeout"] == 60

    def test_unknown_plugin_gets_empty_settings_list(self, svc: PluginService) -> None:
        """build_initial_plugin_settings returns empty settings list for unknown plugins."""
        result = svc.build_initial_plugin_settings(
            active_plugins=["com.example.unknown@0.1.0"],
            system_repo_rows=[],
            org_repo_rows=[],
        )

        entry = result.get("com.example.unknown@0.1.0")
        assert entry is not None
        assert entry["settings"] == []

    def test_multiple_plugins(self, svc: PluginService) -> None:
        """build_initial_plugin_settings handles multiple active plugins."""
        row_a = self._make_plugin_row("com.a", {"x": 1})
        row_b = self._make_plugin_row("com.b", {"y": 2})

        result = svc.build_initial_plugin_settings(
            active_plugins=["com.a@1.0.0", "com.b@2.0.0"],
            system_repo_rows=[row_a, row_b],
            org_repo_rows=[],
        )

        settings_a = {s["key"]: s["value"] for s in result["com.a@1.0.0"]["settings"]}
        settings_b = {s["key"]: s["value"] for s in result["com.b@2.0.0"]["settings"]}
        assert settings_a["x"] == 1
        assert settings_b["y"] == 2


# ---------------------------------------------------------------------------
# Helper converters
# ---------------------------------------------------------------------------


class TestPluginDictConverters:
    """Tests for _system_plugin_to_dict and _org_plugin_to_dict."""

    def test_system_plugin_to_dict_sets_source_system(self) -> None:
        """_system_plugin_to_dict produces source='system'."""
        plugin = MagicMock()
        plugin.id = 1
        plugin.pid = "com.example.x"
        plugin.version = "1.0.0"
        plugin.name = "X"
        plugin.description = None
        plugin.tag = None
        plugin.is_latest = True
        plugin.s3_path = None
        plugin.default_settings = {}
        plugin.capabilities = []
        plugin.agent_type = "specialized"
        plugin.stateless = True

        result = _system_plugin_to_dict(plugin)

        assert result["source"] == "system"
        assert result["pid"] == "com.example.x"
        assert result["is_latest"] is True

    def test_org_plugin_to_dict_sets_source_org(self) -> None:
        """_org_plugin_to_dict produces source='org'."""
        plugin = MagicMock()
        plugin.id = 5
        plugin.pid = "com.example.custom"
        plugin.version = "2.0.0"
        plugin.name = "Custom"
        plugin.description = "desc"
        plugin.tag = "custom"
        plugin.is_latest = False
        plugin.s3_path = "some/path"
        plugin.default_settings = {"k": "v"}
        plugin.capabilities = ["tool"]
        plugin.agent_type = "general"
        plugin.stateless = False

        result = _org_plugin_to_dict(plugin)

        assert result["source"] == "org"
        assert result["default_settings"] == {"k": "v"}
        assert result["is_latest"] is False
