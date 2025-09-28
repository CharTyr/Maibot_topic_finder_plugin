"""Chat stream manager stub."""
from __future__ import annotations

from typing import Dict, Optional

from ...plugin_system import get_logger

logger = get_logger("chat_stream")


class _Stream:
    def __init__(self, stream_id: str, group_id: Optional[str] = None, user_id: Optional[str] = None, is_group: bool = False) -> None:
        self.stream_id = stream_id
        self.group_id = group_id
        self.user_id = user_id
        self.is_group = is_group


class _ChatStreamManager:
    def __init__(self) -> None:
        self._streams: Dict[str, _Stream] = {}

    def register_stream(self, stream: _Stream) -> None:
        self._streams[stream.stream_id] = stream

    def get_stream(self, stream_id: str) -> Optional[_Stream]:
        return self._streams.get(stream_id)


_chat_manager = _ChatStreamManager()


def get_chat_manager() -> _ChatStreamManager:
    return _chat_manager


__all__ = ["get_chat_manager", "_Stream"]
