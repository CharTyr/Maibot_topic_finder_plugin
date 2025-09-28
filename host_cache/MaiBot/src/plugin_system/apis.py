"""Simplified MaiBot API facades used in tests."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import get_logger

logger = get_logger("stub_apis")


class _SendAPI:
    async def text_to_stream(self, text: str, stream_id: Optional[str] = None, **_: Any) -> None:
        logger.info("[send_api] stream=%s text=%s", stream_id or "debug", text)
        await asyncio.sleep(0)


class _MessageAPI:
    def get_messages_by_time_in_chat(
        self,
        chat_id: str,
        start_time: float,
        end_time: float,
        limit: int = 1,
        filter_mai: bool = True,
        filter_command: bool = True,
    ) -> List[Dict[str, Any]]:
        logger.debug(
            "[message_api] get_messages chat_id=%s start=%s end=%s limit=%s",
            chat_id,
            start_time,
            end_time,
            limit,
        )
        return []


@dataclass
class _StreamInfo:
    stream_id: str
    group_id: Optional[str] = None
    user_id: Optional[str] = None
    is_group: bool = False


class _ChatAPI:
    def __init__(self) -> None:
        self._streams: Dict[str, _StreamInfo] = {}

    def register_stream(self, stream_id: str, **kwargs: Any) -> None:
        self._streams[stream_id] = _StreamInfo(stream_id=stream_id, **kwargs)

    def get_group_streams(self) -> List[_StreamInfo]:
        return [stream for stream in self._streams.values() if stream.is_group]

    def get_all_streams(self) -> List[_StreamInfo]:
        return list(self._streams.values())

    def get_stream_by_group_id(self, chat_id: str) -> Optional[_StreamInfo]:
        return next((s for s in self._streams.values() if s.group_id == chat_id), None)

    def get_stream_by_user_id(self, chat_id: str) -> Optional[_StreamInfo]:
        return next((s for s in self._streams.values() if s.user_id == chat_id), None)

    def reset(self) -> None:
        self._streams.clear()


class _LLMAPI:
    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        return {
            "replyer": {
                "model_name": "stub-gpt",
                "temperature": 0.8,
            }
        }

    async def generate_with_model(
        self,
        prompt: str,
        model_config: Dict[str, Any],
        request_type: str,
        temperature: float = 0.9,
        max_tokens: int = 50,
    ) -> Any:
        logger.info(
            "[llm_api] request=%s model=%s", request_type, model_config.get("model_name")
        )
        await asyncio.sleep(0)
        return True, "这是一条示例话题，用于离线测试。", {}, {}


send_api = _SendAPI()
message_api = _MessageAPI()
chat_api = _ChatAPI()
llm_api = _LLMAPI()

__all__ = ["send_api", "message_api", "chat_api", "llm_api"]
