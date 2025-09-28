# Topic Finder Plugin（麦麦找话题插件）

## 概览
- 目标：为群聊定时或在静默时自动发起“吸引注意的一句话话题”。
- 来源：支持 RSS 与 联网大模型（可单独或同时启用，内部并发抓取）。
- 人设：从主程序 `MaiBot/config/bot_config.toml` 的 `[personality]` 读取并注入 Prompt（无需写死在插件）。

## 功能特性
- 定时与静默检测：多时间点定时发送；按群聊覆盖活跃时段；跨午夜时段（如 22–6）。
- 来源与合并策略：`rss.enable_rss`、`web_llm.enable_web_llm` 独立开关；`combine_strategy = merge | prefer_rss | prefer_web`；跨来源去重（按标题归一化）。
- 质量与避重：近 N 小时（默认 48h）以内重复话题避重，必要时重试一次，否则回退备用话题。
- 安全与配置：支持 `WEB_LLM_API_KEY`、`WEB_LLM_BASE_URL` 环境变量覆盖联网大模型配置，避免明文密钥。

## 目录结构（关键文件）
- `plugin.py`：核心逻辑（RSSManager / WebLLMManager / TopicGenerator / 调度与事件）。
- `config.toml`：插件配置（见下方示例）。
- `_manifest.json`：插件清单（version: 1.1.0）。
- `requirements.txt`：最低运行依赖。
- `INSTALL.md`：安装说明（可选）。
- `data/`：缓存与状态文件（运行生成）。
- `logs/`：运行日志（忽略提交）。

## 安装
请查看[INSTALL.md](https://github.com/CharTyr/Maibot_topic_finder_plugin/blob/main/INSTALL.md)

## 配置（`topic_finder_plugin/config.toml`）
```toml
[plugin]
enabled = true

[schedule]
daily_times = ["09:00", "14:00", "20:00"]
enable_daily_schedule = true
min_interval_hours = 2

[silence_detection]
enable_silence_detection = true
silence_threshold_minutes = 60
check_interval_minutes = 10
active_hours_start = 8
active_hours_end = 23

[rss]
enable_rss = true
sources = ["https://www.ithome.com/rss/"]
update_interval_minutes = 30
cache_hours = 6
max_items_per_source = 20

[web_llm]
enable_web_llm = true
base_url = "https://api.perplexity.ai"
api_key = "<建议使用环境变量>"
model_name = "sonar"
temperature = 0.8
max_tokens = 5000
timeout_seconds = 30
# 环境变量覆盖：WEB_LLM_BASE_URL / WEB_LLM_API_KEY

[topic_generation]
# 支持 {persona} 占位；未提供时自动兼容
topic_prompt = """
{persona}
基于下列资讯生成一条能抓住注意力的中文话题钩子：
- 仅输出一句话，不要解释/前后缀/引号/标签/链接
- 26~40 字，包含一个核心名词或趋势词
- 语气克制、轻挑，避免冒犯与敏感内容

资讯：
{rss_content}

输出：
"""
combine_strategy = "merge"
# 备用话题
fallback_topics = ["不说话是吧"]

[filtering]
target_groups = [902106123]
exclude_groups = []
group_only = true

[advanced]
enable_smart_timing = true
max_retry_attempts = 3
debug_mode = false
# 近 N 小时避重窗口与缓存容量
recent_topics_window_hours = 48
recent_topics_max_items = 50

# 群聊覆盖（活跃时间段/静默阈值），支持跨午夜（如 22–6）
[group_overrides]
  [group_overrides."902106123"]
  active_hours_start = 9
  active_hours_end = 22
  silence_threshold_minutes = 45
```

## 使用方式与命令
- 自动：
  - 定时发送：到达 `schedule.daily_times` 检查并发送（按群活跃时段过滤）。
  - 静默检测：群聊无消息超过阈值自动发送（按群活跃时段过滤）。
- 命令：
  - `/topic_test`（测试话题生成）
  - `/topic_config`（查看配置）
  - `/topic_debug`（立即生成并发起话题）
  - `/web_info_test`（测试联网信息获取）

## 数据与缓存
- `data/rss_cache.json`、`data/web_info_cache.json`：来源缓存
- `data/last_update.json`、`data/web_last_update.json`：来源更新时间
- `data/recent_topics.json`：近 N 次发送话题（按群）
- `logs/`：运行日志（建议忽略提交）


```

## 版本
- 当前插件版本：`1.1.0`（见 `_manifest.json`）
- 变更要点：RSS/WebLLM 可独立与并发；跨午夜时段；去重与合并策略；近 N 小时避重；人设从主配置注入。

