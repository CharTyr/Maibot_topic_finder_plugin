import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOST_ROOT = ROOT / "host_cache" / "MaiBot"
if str(HOST_ROOT) not in sys.path:
    sys.path.insert(0, str(HOST_ROOT))

from src.plugin_system.apis import chat_api, send_api  # noqa: E402
from src.plugin_system.core.plugin_manager import plugin_manager  # noqa: E402
from src.manager.async_task_manager import async_task_manager  # noqa: E402
from src.chat.message_receive.chat_stream import get_chat_manager, _Stream  # noqa: E402
from plugin import (
    TopicFinderPlugin,
    TopicSchedulerEventHandler,
    TopicDebugCommand,
)  # noqa: E402


def _minimal_config() -> dict:
    return {
        "plugin": {"enabled": True},
        "schedule": {
            "enable_daily_schedule": True,
            "daily_times": ["00:00"],
            "min_interval_hours": 0,
        },
        "filtering": {
            "target_groups": [],
            "exclude_groups": [],
            "group_only": True,
        },
        "rss": {"enable_rss": False},
        "web_llm": {
            "enable_web_llm": True,
            "api_key": "test-key",
            "model_name": "stub-gpt",
        },
        "topic_generation": {
            "fallback_topics": ["测试备用话题"],
        },
        "silence_detection": {
            "enable_silence_detection": False,
            "active_hours_start": 0,
            "active_hours_end": 23,
        },
        "advanced": {
            "recent_topics_window_hours": 1,
            "recent_topics_max_items": 10,
        },
    }


async def _generate_topic(tmp_path: Path) -> str:
    plugin_manager.reset()
    plugin = TopicFinderPlugin(plugin_dir=str(tmp_path), config=_minimal_config())
    plugin_manager.set_plugin_instance(plugin.plugin_name, plugin)
    return await plugin._generate_topic_content()


def test_topic_generation_smoke(tmp_path):
    result = asyncio.run(_generate_topic(tmp_path))
    assert isinstance(result, str)
    assert result


def test_personality_loading(tmp_path):
    result = asyncio.run(_generate_topic(tmp_path))
    assert "麦" in result or "测试" in result


def test_scheduler_event_registers_task(tmp_path):
    plugin_manager.reset()
    async_task_manager._tasks.clear()
    plugin = TopicFinderPlugin(plugin_dir=str(tmp_path), config=_minimal_config())
    plugin_manager.set_plugin_instance(plugin.plugin_name, plugin)

    handler = TopicSchedulerEventHandler()
    asyncio.run(handler.execute(None))

    assert "topic_scheduler" in async_task_manager._tasks


def test_debug_command_sends_topic(monkeypatch, tmp_path):
    plugin_manager.reset()
    async_task_manager._tasks.clear()
    chat_api.reset()
    get_chat_manager()._streams.clear()

    cfg = _minimal_config()
    cfg["filtering"]["target_groups"] = ["group-1"]

    plugin = TopicFinderPlugin(plugin_dir=str(tmp_path), config=cfg)
    plugin_manager.set_plugin_instance(plugin.plugin_name, plugin)

    chat_api.register_stream("group-1", group_id="group-1", is_group=True)
    get_chat_manager().register_stream(_Stream("group-1", group_id="group-1", is_group=True))

    sent_messages = []

    async def fake_send(text: str, stream_id: str | None = None, **kwargs):
        sent_messages.append((text, stream_id, kwargs))

    monkeypatch.setattr(send_api, "text_to_stream", fake_send)

    command = TopicDebugCommand()
    command.plugin_name = plugin.plugin_name
    command.message = type("Msg", (), {"chat_id": "group-1", "is_group": True})()

    asyncio.run(command.execute())

    assert any("🎯" in text for text, _, _ in sent_messages)
