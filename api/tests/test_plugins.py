"""Tests for the plugin framework and plugin API routes."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — reset registry between tests so decorators don't leak state
# ---------------------------------------------------------------------------

def _reset_registry():
    """Clear the plugin tool registry for test isolation."""
    import api.plugins as plugin_module
    plugin_module._tool_registry.clear()


# ---------------------------------------------------------------------------
# Unit tests: @tool decorator
# ---------------------------------------------------------------------------

class TestToolDecorator:
    def setup_method(self):
        _reset_registry()

    def teardown_method(self):
        _reset_registry()

    def test_decorator_registers_function_by_explicit_name(self):
        from api.plugins import tool, _tool_registry

        @tool(name="my_tool", description="Does something")
        def my_func():
            pass

        assert "my_tool" in _tool_registry
        assert _tool_registry["my_tool"]["function"] is my_func
        assert _tool_registry["my_tool"]["description"] == "Does something"

    def test_decorator_uses_function_name_when_no_name_given(self):
        from api.plugins import tool, _tool_registry

        @tool(description="Auto-named")
        def auto_named_tool():
            pass

        assert "auto_named_tool" in _tool_registry

    def test_decorator_falls_back_to_docstring_for_description(self):
        from api.plugins import tool, _tool_registry

        @tool()
        def docstring_tool():
            """My docstring description."""

        assert _tool_registry["docstring_tool"]["description"] == "My docstring description."

    def test_decorator_returns_original_function(self):
        from api.plugins import tool

        def raw():
            return 42

        wrapped = tool(name="w")(raw)
        assert wrapped is raw
        assert wrapped() == 42

    def test_decorator_records_module(self):
        from api.plugins import tool, _tool_registry

        @tool(name="mod_tool")
        def mod_tool():
            pass

        assert _tool_registry["mod_tool"]["module"] == __name__


# ---------------------------------------------------------------------------
# Unit tests: list_tools
# ---------------------------------------------------------------------------

class TestListTools:
    def setup_method(self):
        _reset_registry()

    def teardown_method(self):
        _reset_registry()

    def test_list_tools_empty_when_no_tools_registered(self):
        from api.plugins import list_tools

        assert list_tools() == []

    def test_list_tools_returns_all_registered(self):
        from api.plugins import tool, list_tools

        @tool(name="alpha", description="First tool")
        def alpha():
            pass

        @tool(name="beta", description="Second tool")
        def beta():
            pass

        tools = list_tools()
        names = {t["name"] for t in tools}
        assert names == {"alpha", "beta"}

    def test_list_tools_entries_have_required_keys(self):
        from api.plugins import tool, list_tools

        @tool(name="check_keys", description="desc")
        def check_keys():
            pass

        entries = list_tools()
        assert len(entries) == 1
        entry = entries[0]
        assert "name" in entry
        assert "description" in entry
        assert "module" in entry


# ---------------------------------------------------------------------------
# Unit tests: get_tool
# ---------------------------------------------------------------------------

class TestGetTool:
    def setup_method(self):
        _reset_registry()

    def teardown_method(self):
        _reset_registry()

    def test_get_tool_returns_callable(self):
        from api.plugins import tool, get_tool

        @tool(name="callable_tool")
        def callable_tool():
            return "result"

        fn = get_tool("callable_tool")
        assert callable(fn)
        assert fn() == "result"

    def test_get_tool_returns_none_for_missing_tool(self):
        from api.plugins import get_tool

        assert get_tool("nonexistent") is None

    def test_get_tool_returns_same_function_reference(self):
        from api.plugins import tool, get_tool

        @tool(name="ref_tool")
        def ref_tool():
            pass

        assert get_tool("ref_tool") is ref_tool


# ---------------------------------------------------------------------------
# Unit tests: load_plugins
# ---------------------------------------------------------------------------

class TestLoadPlugins:
    def setup_method(self):
        _reset_registry()

    def teardown_method(self):
        _reset_registry()

    def test_load_plugins_handles_nonexistent_directory_gracefully(self):
        from api.plugins import load_plugins

        result = load_plugins(Path("/nonexistent/path/that/does/not/exist"))
        assert result == 0

    def test_load_plugins_skips_directories_starting_with_underscore(self, tmp_path):
        from api.plugins import load_plugins

        private_dir = tmp_path / "_private_plugin"
        private_dir.mkdir()
        (private_dir / "plugin.json").write_text('{"name": "Private"}')
        (private_dir / "main.py").write_text("pass")

        result = load_plugins(tmp_path)
        assert result == 0

    def test_load_plugins_skips_dirs_missing_manifest(self, tmp_path):
        from api.plugins import load_plugins

        plugin_dir = tmp_path / "no_manifest"
        plugin_dir.mkdir()
        (plugin_dir / "main.py").write_text("pass")

        result = load_plugins(tmp_path)
        assert result == 0

    def test_load_plugins_skips_dirs_missing_main(self, tmp_path):
        from api.plugins import load_plugins

        plugin_dir = tmp_path / "no_main"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text('{"name": "NoMain", "version": "1.0.0"}')

        result = load_plugins(tmp_path)
        assert result == 0

    def test_load_plugins_handles_broken_module_gracefully(self, tmp_path):
        from api.plugins import load_plugins

        plugin_dir = tmp_path / "broken_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text('{"name": "Broken", "version": "1.0.0"}')
        (plugin_dir / "main.py").write_text("raise ImportError('intentional')")

        # Should not raise; broken plugins are logged as warnings
        result = load_plugins(tmp_path)
        assert result == 0

    def test_load_plugins_returns_count_of_loaded_plugins(self, tmp_path):
        """A plugin with a valid manifest + importable main.py increments the count."""
        from api.plugins import load_plugins

        plugin_dir = tmp_path / "good_plugin"
        plugin_dir.mkdir()
        manifest = {"name": "Good Plugin", "version": "1.0.0"}
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))
        # Minimal main.py that imports successfully
        (plugin_dir / "main.py").write_text("# no tools registered\n")

        # Patch importlib.import_module so the temp path resolves
        fake_module = MagicMock()
        with patch("importlib.import_module", return_value=fake_module) as mock_import:
            result = load_plugins(tmp_path)

        mock_import.assert_called_once()
        assert result == 1


# ---------------------------------------------------------------------------
# Integration tests: plugin API routes
# ---------------------------------------------------------------------------

class TestPluginRoutes:
    def setup_method(self):
        _reset_registry()

    def teardown_method(self):
        _reset_registry()

    @pytest.mark.asyncio
    async def test_list_plugins_returns_empty_when_no_tools(self, client):
        resp = await client.get("/v1/plugins")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["tools"] == []
        assert body["data"]["count"] == 0

    @pytest.mark.asyncio
    async def test_list_plugins_shows_registered_tools(self, client):
        from api.plugins import tool

        @tool(name="route_test_tool", description="Route integration test")
        def route_test_tool():
            pass

        resp = await client.get("/v1/plugins")
        assert resp.status_code == 200
        data = resp.json()["data"]
        names = [t["name"] for t in data["tools"]]
        assert "route_test_tool" in names
        assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_run_tool_404_for_unknown_tool(self, client):
        resp = await client.post("/v1/plugins/does_not_exist/run", json={"arguments": {}})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_run_tool_executes_sync_function(self, client):
        from api.plugins import tool

        @tool(name="sync_add", description="Adds two numbers")
        def sync_add(a: int, b: int) -> int:
            return a + b

        resp = await client.post("/v1/plugins/sync_add/run", json={"arguments": {"a": 3, "b": 4}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["result"] == 7

    @pytest.mark.asyncio
    async def test_run_tool_executes_async_function(self, client):
        from api.plugins import tool

        @tool(name="async_greet", description="Async greeting")
        async def async_greet(name: str) -> str:
            return f"Hello, {name}!"

        resp = await client.post("/v1/plugins/async_greet/run", json={"arguments": {"name": "World"}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["result"] == "Hello, World!"
        assert body["data"]["tool"] == "async_greet"

    @pytest.mark.asyncio
    async def test_run_tool_422_for_bad_arguments(self, client):
        from api.plugins import tool

        @tool(name="strict_args", description="Strict signature")
        def strict_args(required_param: str) -> str:
            return required_param

        # Pass a wrong kwarg name — should get 422
        resp = await client.post(
            "/v1/plugins/strict_args/run",
            json={"arguments": {"wrong_param": "value"}},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_run_tool_500_when_tool_raises(self, client):
        from api.plugins import tool

        @tool(name="always_fails", description="Always raises")
        async def always_fails() -> None:
            raise RuntimeError("deliberate failure")

        resp = await client.post("/v1/plugins/always_fails/run", json={"arguments": {}})
        assert resp.status_code == 500
