"""
麦麦找话题插件

通过RSS订阅和联网模型获取信息，在固定时间或群聊静默时自动发起话题讨论
"""

import asyncio
import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# 尝试导入可选依赖
try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    import aiofiles
except ImportError:
    aiofiles = None

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    import tomllib as toml_lib  # Python 3.11+
except Exception:
    toml_lib = None

try:
    import toml as toml_pkg  # 可选第三方，若存在则作为后备
except Exception:
    toml_pkg = None

from src.plugin_system import (
    BasePlugin, BaseAction, BaseCommand, BaseEventHandler,
    ActionInfo, CommandInfo, EventHandlerInfo,
    ActionActivationType, EventType, ComponentType,
    ConfigField, register_plugin, get_logger,
    MaiMessages, CustomEventHandlerResult
)
from src.plugin_system.apis import (
    send_api, message_api, chat_api, llm_api
)
from src.manager.async_task_manager import AsyncTask, async_task_manager
from src.chat.message_receive.chat_stream import get_chat_manager

logger = get_logger("topic_finder_plugin")


class RSSManager:
    """RSS订阅管理器"""
    
    def __init__(self, plugin_dir: Path, config: Dict[str, Any]):
        self.plugin_dir = plugin_dir
        self.config = config
        self.cache_file = plugin_dir / "data" / "rss_cache.json"
        self.last_update_file = plugin_dir / "data" / "last_update.json"
        
        # 确保数据目录存在
        (plugin_dir / "data").mkdir(exist_ok=True)
    
    async def update_rss_feeds(self) -> List[Dict[str, Any]]:
        """更新RSS订阅源"""
        # 开关：未启用则直接返回
        if not self.config.get("rss", {}).get("enable_rss", True):
            logger.debug("RSS 功能未启用，跳过更新")
            return []
        if not feedparser:
            logger.warning("feedparser未安装，无法解析RSS，将使用备用话题")
            return []

        if not aiohttp:
            logger.warning("aiohttp未安装，无法获取RSS内容，将使用备用话题")
            return []

        all_items = []
        sources = self.config.get("rss", {}).get("sources", [])
        max_items = self.config.get("rss", {}).get("max_items_per_source", 10)

        for source_url in sources:
            try:
                logger.debug(f"获取RSS源: {source_url}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(source_url, timeout=30) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)

                            for entry in feed.entries[:max_items]:
                                item = {
                                    "title": entry.get("title", ""),
                                    "description": entry.get("description", ""),
                                    "link": entry.get("link", ""),
                                    "published": entry.get("published", ""),
                                    "source": source_url,
                                    "timestamp": time.time()
                                }
                                all_items.append(item)
                        else:
                            logger.warning(f"RSS源获取失败: {source_url}, 状态码: {response.status}")
            except Exception as e:
                logger.error(f"获取RSS源失败: {source_url}, 错误: {e}")

        # 保存到缓存
        await self._save_cache(all_items)
        await self._update_last_update_time()

        logger.info(f"RSS更新完成，获取到 {len(all_items)} 条内容")
        return all_items
    
    async def get_cached_items(self, max_age_hours: int = 6) -> List[Dict[str, Any]]:
        """获取缓存的RSS内容"""
        try:
            if not self.cache_file.exists():
                return []
            
            async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                items = json.loads(content)
            
            # 过滤过期内容
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            valid_items = [
                item for item in items
                if current_time - item.get("timestamp", 0) < max_age_seconds
            ]
            
            return valid_items
        except Exception as e:
            logger.error(f"读取RSS缓存失败: {e}")
            return []
    
    async def _save_cache(self, items: List[Dict[str, Any]]):
        """保存RSS缓存"""
        try:
            async with aiofiles.open(self.cache_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(items, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"保存RSS缓存失败: {e}")
    
    async def _update_last_update_time(self):
        """更新最后更新时间"""
        try:
            data = {"last_update": time.time()}
            async with aiofiles.open(self.last_update_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data))
        except Exception as e:
            logger.error(f"更新最后更新时间失败: {e}")
    
    async def should_update(self) -> bool:
        """检查是否需要更新RSS"""
        try:
            # 开关：未启用则不更新
            if not self.config.get("rss", {}).get("enable_rss", True):
                return False
            if not self.last_update_file.exists():
                return True
            
            async with aiofiles.open(self.last_update_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
            
            last_update = data.get("last_update", 0)
            update_interval = self.config.get("rss", {}).get("update_interval_minutes", 30) * 60
            
            return time.time() - last_update > update_interval
        except Exception as e:
            logger.error(f"检查更新时间失败: {e}")
            return True


class WebLLMManager:
    """联网大模型管理器"""

    def __init__(self, plugin_dir: Path, config: Dict[str, Any]):
        self.plugin_dir = plugin_dir
        self.config = config
        self.cache_file = plugin_dir / "data" / "web_info_cache.json"
        self.last_update_file = plugin_dir / "data" / "web_last_update.json"

        # 确保数据目录存在
        (plugin_dir / "data").mkdir(exist_ok=True)

    async def get_web_info(self) -> List[Dict[str, Any]]:
        """获取联网信息"""
        if not self.config.get("web_llm", {}).get("enable_web_llm", False):
            logger.debug("联网大模型功能未启用")
            return []

        # 检查是否需要更新
        if not await self.should_update():
            # 返回缓存的信息
            return await self.get_cached_info()

        try:
            # 调用联网大模型获取信息
            web_info = await self._fetch_web_info()

            # 保存到缓存
            await self._save_cache(web_info)
            await self._update_last_update_time()

            logger.info(f"联网信息获取成功，获取到 {len(web_info)} 条信息")
            return web_info

        except Exception as e:
            logger.error(f"联网信息获取失败: {e}")
            # 返回缓存的信息作为降级
            return await self.get_cached_info()

    async def _fetch_web_info(self) -> List[Dict[str, Any]]:
        """调用联网大模型获取信息"""
        if not aiohttp:
            logger.warning("aiohttp未安装，无法调用联网大模型")
            return []

        web_config = self.config.get("web_llm", {})
        import os
        # 允许通过环境变量覆盖，避免明文写入配置文件
        base_url = os.getenv("WEB_LLM_BASE_URL") or web_config.get("base_url", "")
        api_key = os.getenv("WEB_LLM_API_KEY") or web_config.get("api_key", "")
        model_name = web_config.get("model_name", "gpt-3.5-turbo")
        temperature = web_config.get("temperature", 0.8)
        max_tokens = web_config.get("max_tokens", 500)
        timeout = web_config.get("timeout_seconds", 30)
        prompt_template = web_config.get("web_info_prompt", "请提供最新的热点信息")

        # 插入当前日期
        from datetime import datetime
        current_date = datetime.now().strftime("%Y年%m月%d日")
        prompt = prompt_template.format(current_date=current_date)

        if not base_url or not api_key or api_key == "your-api-key-here":
            logger.warning("联网大模型配置不完整，跳过调用")
            return []

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.post(f"{base_url}/chat/completions", headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                        # 解析返回的内容
                        return self._parse_web_info(content)
                    else:
                        logger.error(f"联网大模型调用失败，状态码: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"联网大模型调用异常: {e}")
            return []

    def _parse_web_info(self, content: str) -> List[Dict[str, Any]]:
        """解析联网大模型返回的信息"""
        info_list = []
        current_time = time.time()

        try:
            # 按行分割内容
            lines = content.strip().split('\n')
            current_item = {}

            for line in lines:
                line = line.strip()
                if not line or line == "---":
                    if current_item.get("title") and current_item.get("description"):
                        current_item["timestamp"] = current_time
                        current_item["source"] = "web_llm"
                        info_list.append(current_item)
                        current_item = {}
                    continue

                if line.startswith("标题：") or line.startswith("标题:"):
                    current_item["title"] = line.replace("标题：", "").replace("标题:", "").strip()
                elif line.startswith("描述：") or line.startswith("描述:"):
                    current_item["description"] = line.replace("描述：", "").replace("描述:", "").strip()

            # 处理最后一个项目
            if current_item.get("title") and current_item.get("description"):
                current_item["timestamp"] = current_time
                current_item["source"] = "web_llm"
                info_list.append(current_item)

        except Exception as e:
            logger.error(f"解析联网信息失败: {e}")

        return info_list

    async def get_cached_info(self) -> List[Dict[str, Any]]:
        """获取缓存的联网信息"""
        try:
            if not self.cache_file.exists():
                return []

            if not aiofiles:
                # 如果aiofiles不可用，使用同步方式
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    items = json.loads(content)
            else:
                async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    items = json.loads(content)

            # 过滤过期内容
            current_time = time.time()
            cache_hours = self.config.get("web_llm", {}).get("web_info_cache_hours", 2)
            max_age_seconds = cache_hours * 3600

            valid_items = [
                item for item in items
                if current_time - item.get("timestamp", 0) < max_age_seconds
            ]

            return valid_items

        except Exception as e:
            logger.error(f"读取联网信息缓存失败: {e}")
            return []

    async def _save_cache(self, items: List[Dict[str, Any]]):
        """保存联网信息缓存"""
        try:
            if not aiofiles:
                # 如果aiofiles不可用，使用同步方式
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(items, ensure_ascii=False, indent=2))
            else:
                async with aiofiles.open(self.cache_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(items, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"保存联网信息缓存失败: {e}")

    async def _update_last_update_time(self):
        """更新最后更新时间"""
        try:
            data = {"last_update": time.time()}
            if not aiofiles:
                with open(self.last_update_file, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(data))
            else:
                async with aiofiles.open(self.last_update_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(data))
        except Exception as e:
            logger.error(f"更新联网信息最后更新时间失败: {e}")

    async def should_update(self) -> bool:
        """检查是否需要更新联网信息"""
        try:
            if not self.last_update_file.exists():
                return True

            if not aiofiles:
                with open(self.last_update_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    data = json.loads(content)
            else:
                async with aiofiles.open(self.last_update_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)

            last_update = data.get("last_update", 0)
            update_interval = self.config.get("web_llm", {}).get("web_info_update_interval", 60) * 60

            return time.time() - last_update > update_interval

        except Exception as e:
            logger.error(f"检查联网信息更新时间失败: {e}")
            return True


class TopicGenerator:
    """话题生成器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def generate_topic(self, rss_items: List[Dict[str, Any]], web_info: List[Dict[str, Any]] = None, persona: Optional[str] = None) -> str:
        """生成话题"""
        try:
            # 准备内容（RSS + 联网信息）
            content = self._prepare_content(rss_items, web_info or [])

            if not content:
                return self._get_fallback_topic()

            # 获取prompt模板
            prompt_template = self.config.get("topic_generation", {}).get(
                "topic_prompt",
                (
                    "你是 MaiBot（有点高冷、玩世不恭的混沌女孩）。\n"
                    "基于下列资讯生成一条能抓住注意力的中文话题钩子：\n"
                    "- 仅输出一句话，不要解释/前后缀/引号/标签/链接\n"
                    "- 26~40 字，包含一个核心名词或趋势词\n"
                    "- 语气克制、轻挑，避免冒犯与敏感内容\n\n"
                    "资讯：\n{rss_content}\n\n"
                    "输出："
                )
            )

            # 注入 persona（若模板未包含 {persona} 也可兼容）
            try:
                prompt = prompt_template.format(rss_content=content, persona=persona or "")
            except KeyError:
                prompt = prompt_template.format(rss_content=content)

            # 获取可用模型
            models = llm_api.get_available_models()
            model_config = models.get("replyer")  # 使用主要回复模型生成话题

            if not model_config:
                logger.warning("未找到'replyer'模型配置，使用备用话题")
                return self._get_fallback_topic()

            # 调用LLM生成话题
            success, response, _, _ = await llm_api.generate_with_model(
                prompt=prompt,
                model_config=model_config,
                request_type="topic.generate",
                temperature=0.9,
                max_tokens=50
            )

            if success and response and response.strip():
                return response.strip()
            else:
                logger.warning(f"LLM生成话题失败或为空，使用备用话题")
                return self._get_fallback_topic()

        except Exception as e:
            logger.error(f"生成话题失败: {e}")
            return self._get_fallback_topic()
    
    def _prepare_content(self, rss_items: List[Dict[str, Any]], web_info: List[Dict[str, Any]]) -> str:
        """准备内容用于生成话题（RSS + 联网信息），支持合并策略与跨来源去重"""
        content_parts: List[str] = []

        # 合并策略：merge / prefer_rss / prefer_web
        combine_strategy = (
            self.config.get("topic_generation", {}).get("combine_strategy", "merge")
        )
        if not isinstance(combine_strategy, str):
            combine_strategy = "merge"
        combine_strategy = combine_strategy.lower()

        def norm_title(t: str) -> str:
            t = (t or "").strip().lower()
            for ch in [" ", "\t", "\n", "-", "_", ",", ".", "!", "?", ":", "；", "，", "。", "！", "？", "：", "·", "—", "~"]:
                t = t.replace(ch, "")
            return t

        seen: set[str] = set()

        # 处理RSS内容
        if rss_items and combine_strategy in ("merge", "prefer_rss"):
            selected_rss = random.sample(rss_items, min(2, len(rss_items)))
            content_parts.append("RSS资讯:")
            for item in selected_rss:
                title = item.get("title", "")
                description = item.get("description", "")[:150]
                key = norm_title(title)
                if title and key not in seen:
                    content_parts.append(f"- {title}")
                    if description:
                        content_parts.append(f"  {description}")
                    seen.add(key)
            content_parts.append("")

        # 处理联网信息
        if web_info and combine_strategy in ("merge", "prefer_web"):
            selected_web = random.sample(web_info, min(2, len(web_info)))
            content_parts.append("联网热点:")
            for item in selected_web:
                title = item.get("title", "")
                description = item.get("description", "")[:150]
                key = norm_title(title)
                if title and key not in seen:
                    content_parts.append(f"- {title}")
                    if description:
                        content_parts.append(f"  {description}")
                    seen.add(key)
            content_parts.append("")

        return "\n".join(content_parts) if content_parts else ""

    def _prepare_rss_content(self, rss_items: List[Dict[str, Any]]) -> str:
        """准备RSS内容用于生成话题（保持向后兼容）"""
        return self._prepare_content(rss_items, [])
    
    def _get_fallback_topic(self) -> str:
        """获取备用话题"""
        fallback_topics = self.config.get("topic_generation", {}).get("fallback_topics", [
            "今天天气不错呢，大家都在忙什么？ ☀️",
            "最近有什么好看的电影或剧推荐吗？ 🎬",
            "周末有什么有趣的计划吗？ 🎉"
        ])
        
        return random.choice(fallback_topics) if fallback_topics else "大家好，来聊聊天吧！ 😊"


class TopicSchedulerTask(AsyncTask):
    """话题调度任务"""
    
    def __init__(self, plugin_instance):
        super().__init__(
            task_name="topic_scheduler",
            wait_before_start=60,  # 启动后1分钟开始检查
            run_interval=300  # 每5分钟检查一次
        )
        self.plugin = plugin_instance
    
    async def run(self):
        """执行定时检查"""
        try:
            await self.plugin._check_scheduled_topics()
        except Exception as e:
            logger.error(f"定时话题检查失败: {e}")


class TopicSchedulerEventHandler(BaseEventHandler):
    """定时话题调度事件处理器"""

    event_type = EventType.ON_START
    handler_name = "topic_scheduler"
    handler_description = "启动话题调度任务"
    weight = 50
    intercept_message = False

    def __init__(self):
        super().__init__()
        self.plugin_instance = None

    async def execute(
        self, message: MaiMessages | None
    ) -> Tuple[bool, bool, Optional[str], Optional[CustomEventHandlerResult], Optional[MaiMessages]]:
        """启动定时任务"""
        try:
            # 获取插件实例
            from src.plugin_system.core.plugin_manager import plugin_manager
            self.plugin_instance = plugin_manager.get_plugin_instance("topic_finder_plugin")

            if not self.plugin_instance:
                logger.error("无法获取话题插件实例")
                return False, True, None, None, None

            # 检查是否启用
            if not self.get_config("plugin.enabled", False):
                logger.info("话题插件未启用")
                return True, True, None, None, None

            # 启动定时任务
            task = TopicSchedulerTask(self.plugin_instance)
            await async_task_manager.add_task(task)

            logger.info("话题调度任务已启动")
            return True, True, None, None, None

        except Exception as e:
            logger.error(f"启动话题调度任务失败: {e}")
            return False, True, None, None, None


class ChatSilenceDetectorEventHandler(BaseEventHandler):
    """群聊静默检测事件处理器"""

    event_type = EventType.ON_MESSAGE
    handler_name = "chat_silence_detector"
    handler_description = "检测群聊静默状态"
    weight = 10
    intercept_message = False

    def __init__(self):
        super().__init__()
        self.last_check_time = {}  # 记录每个群聊的最后检查时间

    def _get_group_override(self, chat_id: Any) -> Dict[str, Any]:
        """获取群聊覆盖配置（若无则返回空字典）"""
        try:
            overrides = self.get_config("group_overrides", {}) or {}
            key = str(chat_id)
            return overrides.get(key, {})
        except Exception:
            return {}

    @staticmethod
    def _in_active_window(current_hour: int, start: int, end: int) -> bool:
        """支持跨午夜的活跃时段判断，例如 22-6 表示 22:00-次日06:00"""
        try:
            start = int(start)
            end = int(end)
            if start <= end:
                return start <= current_hour <= end
            # 跨午夜
            return (current_hour >= start) or (current_hour <= end)
        except Exception:
            return True

    async def execute(
        self, message: MaiMessages | None
    ) -> Tuple[bool, bool, Optional[str], Optional[CustomEventHandlerResult], Optional[MaiMessages]]:
        """检测群聊静默"""
        try:
            if not message:
                return True, True, None, None, None

            # 检查是否启用静默检测
            if not self.get_config("silence_detection.enable_silence_detection", False):
                return True, True, None, None, None

            # 安全地获取消息信息
            msg = None
            chat_id = None
            is_group = False

            # 尝试不同的属性访问方式
            if hasattr(message, 'message_recv') and message.message_recv:
                msg = message.message_recv
                chat_id = getattr(msg, 'chat_id', None)
                is_group = getattr(msg, 'is_group', False)
            elif hasattr(message, 'chat_id'):
                chat_id = message.chat_id
                is_group = getattr(message, 'is_group', False)

            if not chat_id:
                return True, True, None, None, None

            # 只处理群聊
            if not is_group:
                return True, True, None, None, None

            # 检查是否在活跃时间段（支持群聊覆盖）
            current_hour = datetime.now().hour
            override = self._get_group_override(chat_id)
            active_start = override.get("active_hours_start", self.get_config("silence_detection.active_hours_start", 8))
            active_end = override.get("active_hours_end", self.get_config("silence_detection.active_hours_end", 23))

            if not self._in_active_window(current_hour, active_start, active_end):
                return True, True, None, None, None

            # 检查间隔控制
            check_interval = self.get_config("silence_detection.check_interval_minutes", 10) * 60
            current_time = time.time()

            if chat_id in self.last_check_time:
                if current_time - self.last_check_time[chat_id] < check_interval:
                    return True, True, None, None, None

            self.last_check_time[chat_id] = current_time

            # 检查群聊静默时间
            await self._check_chat_silence(chat_id)

            return True, True, None, None, None

        except Exception as e:
            logger.error(f"群聊静默检测失败: {e}")
            return True, True, None, None, None

    async def _check_chat_silence(self, chat_id: str):
        """检查特定群聊的静默状态"""
        try:
            # 支持群聊覆盖静默阈值
            override = self._get_group_override(chat_id)
            silence_minutes = override.get("silence_threshold_minutes", self.get_config("silence_detection.silence_threshold_minutes", 60))
            silence_threshold = int(silence_minutes) * 60
            current_time = time.time()

            # 获取最近的消息
            recent_messages = message_api.get_messages_by_time_in_chat(
                chat_id=chat_id,
                start_time=current_time - silence_threshold,
                end_time=current_time,
                limit=1,
                filter_mai=True,  # 过滤掉麦麦自己的消息
                filter_command=True
            )

            # 如果没有最近消息，说明群聊静默了
            if not recent_messages:
                logger.info(f"检测到群聊 {chat_id} 静默超过阈值，准备发起话题")

                # 获取插件实例并发起话题
                from src.plugin_system.core.plugin_manager import plugin_manager
                plugin_instance = plugin_manager.get_plugin_instance("topic_finder_plugin")

                if plugin_instance:
                    await plugin_instance._send_topic_to_chat(chat_id, reason="群聊静默检测")

        except Exception as e:
            logger.error(f"检查群聊静默状态失败: {e}")


class StartTopicAction(BaseAction):
    """发起话题动作"""

    action_name = "start_topic"
    action_description = "发起一个话题来活跃群聊气氛"
    activation_type = ActionActivationType.KEYWORD

    action_parameters = {
        "topic_content": "要发送的话题内容",
        "reason": "发起话题的原因"
    }
    action_require = [
        "当群聊气氛沉闷需要活跃时使用",
        "当检测到群聊长时间无消息时使用",
        "当需要引发讨论时使用"
    ]
    associated_types = ["text"]

    async def execute(self) -> Tuple[bool, str]:
        """执行发起话题动作"""
        try:
            topic_content = self.action_data.get("topic_content", "")
            reason = self.action_data.get("reason", "发起话题")

            if not topic_content:
                # 如果没有提供话题内容，生成一个
                from src.plugin_system.core.plugin_manager import plugin_manager
                plugin_instance = plugin_manager.get_plugin_instance("topic_finder_plugin")

                if plugin_instance:
                    topic_content = await plugin_instance._generate_topic_content()
                else:
                    topic_content = "大家好，来聊聊天吧！ 😊"

            # 发送话题
            await self.send_text(topic_content)

            logger.info(f"发起话题成功: {reason} - {topic_content[:50]}...")
            return True, f"发起了话题: {reason}"

        except Exception as e:
            logger.error(f"发起话题失败: {e}")
            return False, f"发起话题失败: {str(e)}"


class TopicTestCommand(BaseCommand):
    """测试话题生成命令"""

    command_name = "topic_test"
    command_description = "测试话题生成功能"
    command_usage = "/topic_test - 测试生成一个话题"
    command_pattern = r"^/topic_test$"

    async def execute(self, **kwargs) -> Tuple[bool, str, bool]:
        """执行测试命令"""
        try:
            # 获取插件实例
            from src.plugin_system.core.plugin_manager import plugin_manager
            plugin_instance = plugin_manager.get_plugin_instance("topic_finder_plugin")

            if not plugin_instance:
                await self.send_text("❌ 无法获取话题插件实例")
                return False, "插件实例获取失败", False

            # 生成测试话题
            topic_content = await plugin_instance._generate_topic_content()

            response = f"🎯 测试生成的话题：\n\n{topic_content}"
            await self.send_text(response)

            return True, "话题测试完成", False

        except Exception as e:
            logger.error(f"话题测试失败: {e}")
            await self.send_text(f"❌ 话题测试失败: {str(e)}")
            return False, f"话题测试失败: {str(e)}", False


class TopicConfigCommand(BaseCommand):
    """查看话题配置命令"""

    command_name = "topic_config"
    command_description = "查看话题插件配置信息"
    command_usage = "/topic_config - 查看当前配置"
    command_pattern = r"^/topic_config$"

    async def execute(self, **kwargs) -> Tuple[bool, str, bool]:
        """执行配置查看命令"""
        try:
            # 获取插件实例
            from src.plugin_system.core.plugin_manager import plugin_manager
            plugin_instance = plugin_manager.get_plugin_instance("topic_finder_plugin")

            if not plugin_instance:
                await self.send_text("❌ 无法获取话题插件实例")
                return False, "插件实例获取失败", False

            config = plugin_instance.config

            # 构建配置信息
            config_info = []
            config_info.append("📋 话题插件配置信息：\n")

            # 基本配置
            enabled = config.get("plugin", {}).get("enabled", False)
            config_info.append(f"🔧 插件状态: {'✅ 启用' if enabled else '❌ 禁用'}")

            # 定时配置
            daily_enabled = config.get("schedule", {}).get("enable_daily_schedule", False)
            daily_times = config.get("schedule", {}).get("daily_times", [])
            config_info.append(f"⏰ 定时发送: {'✅ 启用' if daily_enabled else '❌ 禁用'}")
            if daily_times:
                config_info.append(f"   发送时间: {', '.join(daily_times)}")

            # 静默检测配置
            silence_enabled = config.get("silence_detection", {}).get("enable_silence_detection", False)
            silence_threshold = config.get("silence_detection", {}).get("silence_threshold_minutes", 60)
            config_info.append(f"🔇 静默检测: {'✅ 启用' if silence_enabled else '❌ 禁用'}")
            if silence_enabled:
                config_info.append(f"   静默阈值: {silence_threshold} 分钟")

            # RSS配置
            rss_sources = config.get("rss", {}).get("sources", [])
            config_info.append(f"📡 RSS源数量: {len(rss_sources)}")

            # 联网大模型配置
            web_llm_enabled = config.get("web_llm", {}).get("enable_web_llm", False)
            config_info.append(f"🌐 联网大模型: {'✅ 启用' if web_llm_enabled else '❌ 禁用'}")

            # 目标群聊配置
            target_groups = config.get("filtering", {}).get("target_groups", [])
            if target_groups:
                config_info.append(f"🎯 目标群聊: {len(target_groups)} 个")

            response = "\n".join(config_info)
            await self.send_text(response)

            return True, "配置查看完成", False

        except Exception as e:
            logger.error(f"查看配置失败: {e}")
            await self.send_text(f"❌ 查看配置失败: {str(e)}")
            return False, f"查看配置失败: {str(e)}", False


class TopicDebugCommand(BaseCommand):
    """调试话题生成命令"""

    command_name = "topic_debug"
    command_description = "立即生成并发起话题（调试用）"
    command_usage = "/topic_debug - 立即发起话题"
    command_pattern = r"^/topic_debug$"

    async def execute(self, **kwargs) -> Tuple[bool, str, bool]:
        """执行调试命令"""
        try:
            # 获取插件实例
            from src.plugin_system.core.plugin_manager import plugin_manager
            plugin_instance = plugin_manager.get_plugin_instance("topic_finder_plugin")

            if not plugin_instance:
                await self.send_text("❌ 无法获取话题插件实例")
                return False, "插件实例获取失败", False

            # 检查插件是否启用
            if not plugin_instance.get_config("plugin.enabled", False):
                await self.send_text("❌ 话题插件未启用")
                return False, "插件未启用", False

            await self.send_text("🔄 正在生成话题...")

            # 生成话题内容
            topic_content = await plugin_instance._generate_topic_content()

            if not topic_content:
                await self.send_text("❌ 话题生成失败")
                return False, "话题生成失败", False

            # 发送话题
            await self.send_text(f"🎯 调试生成的话题：\n\n{topic_content}")

            # 记录调试发送时间
            current_time = time.time()
            # 安全地获取chat_id
            chat_id = "unknown"
            if hasattr(self, 'message') and self.message:
                chat_id = getattr(self.message, 'chat_id', 'unknown')
            elif hasattr(self, 'chat_id'):
                chat_id = self.chat_id

            plugin_instance.last_topic_time[chat_id] = current_time

            logger.info(f"调试话题发送成功: {chat_id} - {topic_content[:50]}...")

            return True, "调试话题发送完成", False

        except Exception as e:
            logger.error(f"调试话题生成失败: {e}")
            await self.send_text(f"❌ 调试话题生成失败: {str(e)}")
            return False, f"调试话题生成失败: {str(e)}", False


class WebInfoTestCommand(BaseCommand):
    """测试联网信息获取命令"""

    command_name = "web_info_test"
    command_description = "测试联网大模型信息获取功能"
    command_usage = "/web_info_test - 测试获取联网信息"
    command_pattern = r"^/web_info_test$"

    async def execute(self, **kwargs) -> Tuple[bool, str, bool]:
        """执行联网信息测试命令"""
        try:
            # 获取插件实例
            from src.plugin_system.core.plugin_manager import plugin_manager
            plugin_instance = plugin_manager.get_plugin_instance("topic_finder_plugin")

            if not plugin_instance:
                await self.send_text("❌ 无法获取话题插件实例")
                return False, "插件实例获取失败", False

            # 检查联网大模型是否启用
            if not plugin_instance.get_config("web_llm.enable_web_llm", False):
                await self.send_text("❌ 联网大模型功能未启用")
                return False, "联网大模型功能未启用", False

            await self.send_text("🔄 正在获取联网信息...")

            # 获取联网信息
            if not plugin_instance.web_llm_manager:
                await self.send_text("❌ 联网大模型管理器未初始化")
                return False, "联网大模型管理器未初始化", False

            web_info = await plugin_instance.web_llm_manager.get_web_info()

            if not web_info:
                await self.send_text("❌ 未获取到联网信息，请检查配置")
                return False, "未获取到联网信息", False

            # 构建响应信息
            response_parts = [f"🌐 联网信息获取成功，共 {len(web_info)} 条信息：\n"]

            for i, info in enumerate(web_info[:3], 1):  # 只显示前3条
                title = info.get("title", "无标题")
                description = info.get("description", "无描述")[:100]  # 限制长度
                response_parts.append(f"{i}. {title}")
                if description:
                    response_parts.append(f"   {description}...")
                response_parts.append("")

            if len(web_info) > 3:
                response_parts.append(f"... 还有 {len(web_info) - 3} 条信息")

            response = "\n".join(response_parts)
            await self.send_text(response)

            return True, "联网信息测试完成", False

        except Exception as e:
            logger.error(f"联网信息测试失败: {e}")
            await self.send_text(f"❌ 联网信息测试失败: {str(e)}")
            return False, f"联网信息测试失败: {str(e)}", False


@register_plugin
class TopicFinderPlugin(BasePlugin):
    """麦麦找话题插件"""

    plugin_name: str = "topic_finder_plugin"
    enable_plugin: bool = True
    dependencies: list[str] = []
    python_dependencies: list[str] = ["feedparser>=6.0.10", "aiofiles>=23.0.0", "aiohttp>=3.8.0"]
    config_file_name: str = "config.toml"

    config_schema: dict = {
        "plugin": {
            "enabled": ConfigField(bool, default=True, description="是否启用插件"),
            "config_version": ConfigField(str, default="1.0.0", description="配置文件版本"),
        },
        "schedule": {
            "daily_times": ConfigField(list, default=["09:00", "14:00", "20:00"], description="每日发送话题的时间点"),
            "enable_daily_schedule": ConfigField(bool, default=True, description="是否启用定时发送"),
            "min_interval_hours": ConfigField(int, default=2, description="话题发送最小间隔（小时）"),
        },
        "silence_detection": {
            "enable_silence_detection": ConfigField(bool, default=True, description="是否启用群聊静默检测"),
            "silence_threshold_minutes": ConfigField(int, default=60, description="群聊静默时间阈值（分钟）"),
            "check_interval_minutes": ConfigField(int, default=10, description="检查间隔（分钟）"),
            "active_hours_start": ConfigField(int, default=8, description="活跃时间段开始"),
            "active_hours_end": ConfigField(int, default=23, description="活跃时间段结束"),
        },
        "rss": {
            "enable_rss": ConfigField(bool, default=True, description="是否启用RSS订阅源"),
            "sources": ConfigField(list, default=[], description="RSS订阅源列表"),
            "update_interval_minutes": ConfigField(int, default=30, description="RSS更新间隔（分钟）"),
            "cache_hours": ConfigField(int, default=6, description="RSS内容缓存时间（小时）"),
            "max_items_per_source": ConfigField(int, default=10, description="每次获取的最大条目数"),
        },
        "topic_generation": {
            "topic_prompt": ConfigField(str, default="", description="话题生成的prompt模板"),
            "fallback_topics": ConfigField(list, default=[], description="备用话题列表"),
            "combine_strategy": ConfigField(str, default="merge", description="内容合并策略：merge/prefer_rss/prefer_web"),
        },
        "filtering": {
            "target_groups": ConfigField(list, default=[], description="目标群聊列表"),
            "exclude_groups": ConfigField(list, default=[], description="排除的群聊列表"),
            "group_only": ConfigField(bool, default=True, description="是否只在群聊中发送"),
        },
        "web_llm": {
            "enable_web_llm": ConfigField(bool, default=True, description="是否启用联网大模型"),
            "base_url": ConfigField(str, default="https://api.openai.com/v1", description="联网大模型API基础URL"),
            "api_key": ConfigField(str, default="your-api-key-here", description="联网大模型API密钥"),
            "model_name": ConfigField(str, default="gpt-3.5-turbo", description="联网大模型名称"),
            "temperature": ConfigField(float, default=0.8, description="联网大模型温度参数"),
            "max_tokens": ConfigField(int, default=500, description="联网大模型最大token数"),
            "timeout_seconds": ConfigField(int, default=30, description="联网大模型请求超时时间"),
            "web_info_prompt": ConfigField(str, default="", description="联网信息获取prompt"),
            "web_info_update_interval": ConfigField(int, default=60, description="联网信息更新间隔（分钟）"),
            "web_info_cache_hours": ConfigField(int, default=2, description="联网信息缓存时间（小时）"),
        },
        "advanced": {
            "enable_smart_timing": ConfigField(bool, default=True, description="是否启用智能时机检测"),
            "max_retry_attempts": ConfigField(int, default=3, description="最大重试次数"),
            "debug_mode": ConfigField(bool, default=False, description="调试模式"),
            "recent_topics_window_hours": ConfigField(int, default=48, description="近N小时内避免重复话题"),
            "recent_topics_max_items": ConfigField(int, default=50, description="最近话题缓存的最大条目数/每群"),
        },
        # 按群覆盖：active_hours_start/end、silence_threshold_minutes
        "group_overrides": ConfigField(dict, default={}, description="群聊级别的活跃时段与静默阈值覆盖"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rss_manager = None
        self.web_llm_manager = None
        self.topic_generator = None
        self.last_topic_time = {}  # 记录每个群聊最后发送话题的时间
        self.last_scheduled_check = 0  # 记录最后一次定时检查的时间
        self._persona_cache: Optional[str] = None
        self._recent_topics_path = None

        # 初始化管理器
        if self.plugin_dir:
            self.rss_manager = RSSManager(Path(self.plugin_dir), self.config)
            self.web_llm_manager = WebLLMManager(Path(self.plugin_dir), self.config)
            self.topic_generator = TopicGenerator(self.config)
            self._recent_topics_path = Path(self.plugin_dir) / "data" / "recent_topics.json"

    def get_plugin_components(self) -> List[Tuple[Any, type]]:
        """获取插件组件"""
        components = []

        if self.get_config("plugin.enabled", True):
            # 添加事件处理器
            components.append((TopicSchedulerEventHandler.get_handler_info(), TopicSchedulerEventHandler))

            if self.get_config("silence_detection.enable_silence_detection", True):
                components.append((ChatSilenceDetectorEventHandler.get_handler_info(), ChatSilenceDetectorEventHandler))

            # 添加动作组件
            components.append((StartTopicAction.get_action_info(), StartTopicAction))

            # 添加命令组件
            components.append((TopicTestCommand.get_command_info(), TopicTestCommand))
            components.append((TopicConfigCommand.get_command_info(), TopicConfigCommand))
            components.append((TopicDebugCommand.get_command_info(), TopicDebugCommand))
            components.append((WebInfoTestCommand.get_command_info(), WebInfoTestCommand))

        return components

    async def _check_scheduled_topics(self):
        """检查定时话题发送"""
        try:
            if not self.get_config("schedule.enable_daily_schedule", True):
                return

            current_time = datetime.now()
            current_time_str = current_time.strftime("%H:%M")

            # 检查是否已经在这个时间点检查过了（避免重复发送）
            current_minute = current_time.hour * 60 + current_time.minute
            if abs(current_minute - self.last_scheduled_check) < 5:  # 5分钟内不重复检查
                return

            daily_times = self.get_config("schedule.daily_times", [])

            for scheduled_time in daily_times:
                try:
                    scheduled_hour, scheduled_minute = map(int, scheduled_time.split(":"))
                    scheduled_minute_total = scheduled_hour * 60 + scheduled_minute

                    # 检查是否到了发送时间（允许5分钟误差）
                    if abs(current_minute - scheduled_minute_total) <= 5:
                        logger.info(f"到达定时发送时间: {scheduled_time}")
                        await self._send_scheduled_topics()
                        self.last_scheduled_check = current_minute
                        break

                except ValueError:
                    logger.error(f"无效的时间格式: {scheduled_time}")

        except Exception as e:
            logger.error(f"检查定时话题失败: {e}")

    async def _send_scheduled_topics(self):
        """发送定时话题到所有目标群聊"""
        try:
            # 获取目标群聊列表
            target_groups = self.get_config("filtering.target_groups", [])
            exclude_groups = self.get_config("filtering.exclude_groups", [])
            group_only = self.get_config("filtering.group_only", True)

            # 获取所有群聊
            if not target_groups:
                # 如果没有指定目标群聊，获取所有群聊
                all_streams = chat_api.get_group_streams() if group_only else chat_api.get_all_streams()
                target_chats = [stream.stream_id for stream in all_streams]
            else:
                target_chats = target_groups

            # 过滤排除的群聊
            target_chats = [chat_id for chat_id in target_chats if chat_id not in exclude_groups]

            # 发送话题到每个目标群聊（尊重群聊活跃时段覆盖）
            now_hour = datetime.now().hour
            overrides = self.get_config("group_overrides", {}) or {}

            def in_window(hour: int, start: int, end: int) -> bool:
                if start <= end:
                    return start <= hour <= end
                return (hour >= start) or (hour <= end)

            for chat_id in target_chats:
                ov = overrides.get(str(chat_id), {})
                active_start = ov.get("active_hours_start", self.get_config("silence_detection.active_hours_start", 8))
                active_end = ov.get("active_hours_end", self.get_config("silence_detection.active_hours_end", 23))

                if not in_window(now_hour, active_start, active_end):
                    logger.debug(f"群聊 {chat_id} 当前不在活跃时段[{active_start}-{active_end}]，跳过定时发送")
                    continue

                await self._send_topic_to_chat(chat_id, reason="定时发送")

        except Exception as e:
            logger.error(f"发送定时话题失败: {e}")

    async def _send_topic_to_chat(self, chat_id: str, reason: str = "话题发送"):
        """发送话题到指定群聊"""
        try:
            # 检查发送间隔
            min_interval = self.get_config("schedule.min_interval_hours", 2) * 3600
            current_time = time.time()

            if chat_id in self.last_topic_time:
                if current_time - self.last_topic_time[chat_id] < min_interval:
                    logger.debug(f"群聊 {chat_id} 话题发送间隔未到，跳过")
                    return

            # 生成话题内容
            topic_content = await self._generate_topic_content()

            # 近N小时去重：如重复，重试一次，否则使用备用话题
            if await self._is_recent_duplicate(chat_id, topic_content):
                logger.info(f"检测到与近时段内话题重复，进行一次重试: {chat_id}")
                retry = await self._generate_topic_content()
                if retry and not await self._is_recent_duplicate(chat_id, retry):
                    topic_content = retry
                else:
                    topic_content = self.topic_generator._get_fallback_topic()

            if not topic_content:
                logger.warning(f"无法生成话题内容，跳过群聊 {chat_id}")
                return

            # 发送话题
            stream_id = str(chat_id)
            stream = get_chat_manager().get_stream(stream_id)
            if not stream:
                stream_obj = chat_api.get_stream_by_group_id(str(chat_id))
                if not stream_obj:
                    stream_obj = chat_api.get_stream_by_user_id(str(chat_id))
                if not stream_obj:
                    logger.error(f"发送话题到群聊失败: 未找到聊天流 {chat_id}")
                    return
                stream_id = stream_obj.stream_id

            await send_api.text_to_stream(
                text=topic_content,
                stream_id=stream_id,
                typing=False,
                storage_message=True,
            )

            # 记录发送时间
            self.last_topic_time[chat_id] = current_time
            await self._record_recent_topic(chat_id, topic_content)

            logger.info(f"话题发送成功 - {reason}: {chat_id} - {topic_content[:50]}...")

        except Exception as e:
            logger.error(f"发送话题到群聊失败: {chat_id} - {e}")

    async def _generate_topic_content(self) -> str:
        """生成话题内容"""
        try:
            if not self.topic_generator:
                return "不说话是吧"

            rss_items: List[Dict[str, Any]] = []
            web_info: List[Dict[str, Any]] = []

            use_rss = bool(self.get_config("rss.enable_rss", True) and self.rss_manager)
            use_web = bool(self.get_config("web_llm.enable_web_llm", False) and self.web_llm_manager)

            # 若两个来源都未启用，直接返回备用话题
            if not use_rss and not use_web:
                logger.info("RSS 与 联网大模型均未启用，使用备用话题")
                return self.topic_generator._get_fallback_topic()

            async def get_rss_items() -> List[Dict[str, Any]]:
                if not use_rss:
                    return []
                # 检查是否需要更新RSS
                if await self.rss_manager.should_update():
                    logger.info("开始更新RSS订阅源...")
                    await self.rss_manager.update_rss_feeds()
                # 获取缓存的RSS内容
                cache_hours_local = self.get_config("rss.cache_hours", 6)
                return await self.rss_manager.get_cached_items(cache_hours_local)

            async def get_web_items() -> List[Dict[str, Any]]:
                if not use_web:
                    return []
                logger.info("开始获取联网信息...")
                return await self.web_llm_manager.get_web_info()

            # 并发抓取，缩短等待时间
            tasks = []
            if use_rss:
                tasks.append(get_rss_items())
            if use_web:
                tasks.append(get_web_items())

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                idx = 0
                if use_rss:
                    rss_result = results[idx]; idx += 1
                    if isinstance(rss_result, Exception):
                        logger.error(f"RSS 获取异常: {rss_result}")
                        rss_items = []
                    else:
                        rss_items = rss_result or []
                if use_web:
                    web_result = results[idx if use_rss else 0]
                    if isinstance(web_result, Exception):
                        logger.error(f"联网信息获取异常: {web_result}")
                        web_info = []
                    else:
                        web_info = web_result or []

            # 生成话题（依据启用的来源合并内容），注入主程序人设
            persona = await self._get_personality()
            topic_content = await self.topic_generator.generate_topic(rss_items, web_info, persona=persona)

            return topic_content

        except Exception as e:
            logger.error(f"生成话题内容失败: {e}")
            return "不说话是吧"

    async def _get_personality(self) -> str:
        """从主程序 bot_config.toml 读取 personality 文本，失败则返回空字符串并不影响生成"""
        try:
            if self._persona_cache is not None:
                return self._persona_cache

            base_dir = Path(self.plugin_dir).parent if self.plugin_dir else Path.cwd()
            bot_cfg = base_dir / "MaiBot" / "config" / "bot_config.toml"
            if bot_cfg.exists():
                data = None
                if toml_lib is not None:
                    with open(bot_cfg, 'rb') as f:
                        data = toml_lib.load(f)
                elif toml_pkg is not None:
                    data = toml_pkg.load(str(bot_cfg))
                else:
                    return ""
                p = data.get("personality", {}).get("personality", "")
                reply_style = data.get("personality", {}).get("reply_style", "")
                persona_text = p.strip()
                if reply_style:
                    persona_text = f"{persona_text}。说话风格：{reply_style.strip()}"
                self._persona_cache = persona_text
                return persona_text
        except Exception as e:
            logger.warning(f"读取主程序personality失败: {e}")
        return ""

    async def _load_recent_topics(self) -> Dict[str, List[Dict[str, Any]]]:
        try:
            path = self._recent_topics_path
            if not path or not path.exists():
                return {}
            if aiofiles:
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    content = await f.read()
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            return json.loads(content or "{}")
        except Exception:
            return {}

    async def _save_recent_topics(self, data: Dict[str, List[Dict[str, Any]]]):
        try:
            path = self._recent_topics_path
            if not path:
                return
            if aiofiles:
                async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(data, ensure_ascii=False))
            else:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"保存最近话题失败: {e}")

    def _norm_text(self, s: str) -> str:
        s = (s or "").strip().lower()
        for ch in [" ", "\t", "\n", "-", "_", ",", ".", "!", "?", ":", "；", "，", "。", "！", "？", "：", "·", "—", "~"]:
            s = s.replace(ch, "")
        return s

    async def _is_recent_duplicate(self, chat_id: str, content: Optional[str]) -> bool:
        if not content:
            return False
        try:
            data = await self._load_recent_topics()
            items = data.get(str(chat_id), [])
            win_hours = int(self.get_config("advanced.recent_topics_window_hours", 48))
            cutoff = time.time() - win_hours * 3600
            norm_c = self._norm_text(content)
            for it in items:
                if it.get('ts', 0) >= cutoff:
                    if self._norm_text(it.get('content', '')) == norm_c:
                        return True
            return False
        except Exception:
            return False

    async def _record_recent_topic(self, chat_id: str, content: Optional[str]):
        if not content:
            return
        try:
            data = await self._load_recent_topics()
            items = data.get(str(chat_id), [])
            items.append({"content": content, "ts": time.time()})
            max_keep = int(self.get_config("advanced.recent_topics_max_items", 50))
            items = items[-max_keep:]
            data[str(chat_id)] = items
            await self._save_recent_topics(data)
        except Exception as e:
            logger.error(f"记录最近话题失败: {e}")
