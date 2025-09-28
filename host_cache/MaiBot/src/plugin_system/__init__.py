"""Minimal plugin system stubs to exercise the topic finder plugin offline."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

__all__ = [
    "ActionActivationType",
    "EventType",
    "ComponentType",
    "ActionInfo",
    "CommandInfo",
    "EventHandlerInfo",
    "ConfigField",
    "MaiMessages",
    "CustomEventHandlerResult",
    "BasePlugin",
    "BaseAction",
    "BaseCommand",
    "BaseEventHandler",
    "register_plugin",
    "get_logger",
]


class ActionActivationType(Enum):
    """Simplified enumeration for action trigger types."""

    KEYWORD = "keyword"
    PASSIVE = "passive"


class EventType(Enum):
    """Supported event hooks."""

    ON_START = "on_start"
    ON_MESSAGE = "on_message"


class ComponentType(Enum):
    """Categories of plugin components."""

    ACTION = auto()
    COMMAND = auto()
    EVENT_HANDLER = auto()


@dataclass
class ActionInfo:
    name: str
    description: str = ""
    activation_type: ActionActivationType = ActionActivationType.KEYWORD


@dataclass
class CommandInfo:
    name: str
    description: str = ""
    usage: str = ""


@dataclass
class EventHandlerInfo:
    name: str
    description: str = ""
    event_type: EventType = EventType.ON_MESSAGE
    component_type: ComponentType = ComponentType.EVENT_HANDLER


@dataclass
class ConfigField:
    field_type: type
    default: Any = None
    description: str = ""


@dataclass
class CustomEventHandlerResult:
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MaiMessages:
    """Light-weight message container used by the stubs."""

    chat_id: Optional[str] = None
    is_group: bool = False
    message_recv: Any = None


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger."""

    logger = logging.getLogger(name)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    return logger


class BaseComponent:
    """Shared helper for commands, actions and event handlers."""

    plugin_name: str = "topic_finder_plugin"

    def __init__(self) -> None:
        self.logger = get_logger(self.__class__.__name__)

    def _get_plugin(self) -> Optional["BasePlugin"]:
        from .core.plugin_manager import plugin_manager

        return plugin_manager.get_plugin_instance(self.plugin_name)

    def get_config(self, path: str, default: Any = None) -> Any:
        plugin = self._get_plugin()
        if not plugin:
            return default
        return plugin.get_config(path, default)

    async def send_text(self, text: str, **_: Any) -> None:
        plugin = self._get_plugin()
        if plugin:
            await plugin.send_text(text)
        else:
            self.logger.info("[send_text] %s", text)


class BasePlugin:
    """Minimal plugin base class."""

    plugin_name: str = ""
    config_schema: Dict[str, Any] = {}

    def __init__(self, plugin_dir: Optional[str] = None, config: Optional[Dict[str, Any]] = None, **_: Any) -> None:
        self.plugin_dir = plugin_dir
        self.config = config or {}
        self.logger = get_logger(self.plugin_name or self.__class__.__name__)

    def get_config(self, path: str, default: Any = None) -> Any:
        data: Any = self.config
        for key in path.split("."):
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data

    async def send_text(self, text: str, stream_id: Optional[str] = None, **_: Any) -> None:
        from .apis import send_api

        await send_api.text_to_stream(text=text, stream_id=stream_id or "debug")


class BaseAction(BaseComponent):
    action_data: Dict[str, Any]

    def __init__(self, action_data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        super().__init__()
        self.action_data = action_data or {}

    @classmethod
    def get_action_info(cls) -> ActionInfo:
        return ActionInfo(name=getattr(cls, "action_name", cls.__name__), description=getattr(cls, "action_description", ""))


class BaseCommand(BaseComponent):
    message: Optional[MaiMessages]

    def __init__(self, message: Optional[MaiMessages] = None, **kwargs: Any) -> None:
        super().__init__()
        self.message = message

    @classmethod
    def get_command_info(cls) -> CommandInfo:
        return CommandInfo(
            name=getattr(cls, "command_name", cls.__name__),
            description=getattr(cls, "command_description", ""),
            usage=getattr(cls, "command_usage", ""),
        )


class BaseEventHandler(BaseComponent):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__()

    @classmethod
    def get_handler_info(cls) -> EventHandlerInfo:
        return EventHandlerInfo(
            name=getattr(cls, "handler_name", cls.__name__),
            description=getattr(cls, "handler_description", ""),
            event_type=getattr(cls, "event_type", EventType.ON_MESSAGE),
        )


def register_plugin(cls: type[BasePlugin]) -> type[BasePlugin]:
    """Decorator registering the plugin class to the stub manager."""

    from .core.plugin_manager import plugin_manager

    plugin_manager.register_plugin_class(cls)
    return cls
