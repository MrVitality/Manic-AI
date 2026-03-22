"""Plugin system for custom agent tools.

Plugins are auto-discovered from the api/plugins/ directory at startup.
Each plugin directory must contain a plugin.json manifest and a main.py
with @tool decorated functions.
"""

import json
import importlib
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Registry of all loaded tools
_tool_registry: Dict[str, Dict[str, Any]] = {}


def tool(name: str = None, description: str = ""):
    """Decorator to register a function as a plugin tool."""
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        _tool_registry[tool_name] = {
            "name": tool_name,
            "description": description or func.__doc__ or "",
            "function": func,
            "module": func.__module__,
        }
        return func
    return decorator


def get_tool(name: str) -> Optional[Callable]:
    """Get a registered tool by name."""
    entry = _tool_registry.get(name)
    return entry["function"] if entry else None


def list_tools() -> List[Dict[str, str]]:
    """List all registered tools."""
    return [
        {"name": t["name"], "description": t["description"], "module": t["module"]}
        for t in _tool_registry.values()
    ]


def load_plugins(plugins_dir: Path = None) -> int:
    """Auto-discover and load all plugins.

    Returns the number of plugins successfully loaded.
    """
    if plugins_dir is None:
        plugins_dir = Path(__file__).parent

    if not plugins_dir.exists():
        logger.warning("Plugins directory does not exist: %s", plugins_dir)
        return 0

    loaded = 0
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
            continue

        manifest_path = plugin_dir / "plugin.json"
        main_path = plugin_dir / "main.py"

        if not manifest_path.exists() or not main_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            module_name = f"api.plugins.{plugin_dir.name}.main"
            importlib.import_module(module_name)
            loaded += 1
            logger.info(
                "Loaded plugin: %s v%s",
                manifest.get("name"),
                manifest.get("version"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load plugin %s: %s", plugin_dir.name, exc)

    logger.info("Loaded %d plugins with %d tools", loaded, len(_tool_registry))
    return loaded
