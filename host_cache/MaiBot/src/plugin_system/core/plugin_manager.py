"""A tiny plugin manager used solely for offline tests."""
from __future__ import annotations

from typing import Any, Dict, Optional, Type

from .. import BasePlugin, get_logger


class PluginManager:
    def __init__(self) -> None:
        self._logger = get_logger("plugin_manager")
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}
        self._plugin_instances: Dict[str, BasePlugin] = {}

    # Registration -----------------------------------------------------
    def register_plugin_class(self, plugin_cls: Type[BasePlugin]) -> None:
        name = getattr(plugin_cls, "plugin_name", plugin_cls.__name__)
        self._plugin_classes[name] = plugin_cls
        self._logger.debug("Registered plugin class: %s", name)

    # Instantiation ----------------------------------------------------
    def ensure_plugin(self, plugin_name: str, **kwargs: Any) -> BasePlugin:
        if plugin_name in self._plugin_instances:
            return self._plugin_instances[plugin_name]
        plugin_cls = self._plugin_classes.get(plugin_name)
        if not plugin_cls:
            raise KeyError(f"Plugin {plugin_name!r} is not registered")
        instance = plugin_cls(**kwargs)
        self._plugin_instances[plugin_name] = instance
        return instance

    def set_plugin_instance(self, plugin_name: str, instance: BasePlugin) -> None:
        self._plugin_instances[plugin_name] = instance

    # Retrieval --------------------------------------------------------
    def get_plugin_instance(self, plugin_name: str) -> Optional[BasePlugin]:
        return self._plugin_instances.get(plugin_name)

    def reset(self) -> None:
        self._plugin_instances.clear()


plugin_manager = PluginManager()

__all__ = ["plugin_manager", "PluginManager"]
