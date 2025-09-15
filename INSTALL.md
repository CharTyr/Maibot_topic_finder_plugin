# 麦麦找话题插件 - 安装指南

## 📦 插件安装

### 1. 确认插件位置
插件应该位于 MaiBot 的 `plugins/` 目录下：
```
MaiBot/
└── plugins/
    └── topic_finder_plugin/
        ├── plugin.py
        ├── config.toml
        ├── _manifest.json
        ├── requirements.txt
        └── ...
```

### 2. 安装依赖
进入 MaiBot 目录并激活虚拟环境：
```bash
cd MaiBot
source venv/bin/activate
pip install feedparser aiofiles
```

或者使用插件的 requirements.txt：
```bash
cd MaiBot/plugins/topic_finder_plugin
pip install -r requirements.txt
```

### 3. 验证安装
运行测试脚本验证插件是否正常工作：
```bash
cd MaiBot/plugins/topic_finder_plugin
python test_plugin.py
```

## ⚙️ 配置插件

### 1. 基础配置
编辑 `config.toml` 文件：

```toml
[plugin]
enabled = true  # 启用插件

[schedule]
daily_times = ["09:00", "14:00", "20:00"]  # 发送时间
enable_daily_schedule = true
min_interval_hours = 2

[silence_detection]
enable_silence_detection = true
silence_threshold_minutes = 60
active_hours_start = 8
active_hours_end = 23
```

### 2. RSS源配置
添加你想要的RSS源：

```toml
[rss]
sources = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss",
    "https://www.zhihu.com/rss"
]
```

### 3. 话题生成配置
自定义话题生成prompt和备用话题：

```toml
[topic_generation]
fallback_topics = [
    "今天天气不错呢，大家都在忙什么？ ☀️",
    "最近有什么好看的电影推荐吗？ 🎬",
    "周末有什么有趣的计划吗？ 🎉"
]
```

## 🚀 启动插件

### 1. 重启 MaiBot
插件会在 MaiBot 启动时自动加载。

### 2. 验证插件状态
在群聊中使用命令验证：
```
/topic_config
```

应该看到插件配置信息。

### 3. 测试功能
使用测试命令：
```
/topic_test
```

应该看到生成的测试话题。

## 🔧 故障排除

### 插件未加载
1. 检查插件目录结构是否正确
2. 确认 `_manifest.json` 文件存在且格式正确
3. 查看 MaiBot 启动日志中的错误信息

### 依赖缺失
```bash
# 重新安装依赖
pip install feedparser aiofiles

# 验证依赖
python -c "import feedparser, aiofiles; print('依赖安装成功')"
```

### RSS获取失败
1. 检查网络连接
2. 尝试更换RSS源
3. 插件会自动使用备用话题

### 话题不发送
1. 确认插件已启用：`/topic_config`
2. 检查时间配置是否正确
3. 确认群聊在目标列表中

## 📝 配置示例

### 完整配置示例
```toml
[plugin]
enabled = true
config_version = "1.0.0"

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
sources = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.cnn.com/rss/edition.rss"
]
update_interval_minutes = 30
cache_hours = 6
max_items_per_source = 10

[topic_generation]
fallback_topics = [
    "今天天气不错呢，大家都在忙什么？ ☀️",
    "最近有什么好看的电影推荐吗？ 🎬"
]

[filtering]
target_groups = []
exclude_groups = []
group_only = true

[advanced]
enable_smart_timing = true
max_retry_attempts = 3
debug_mode = false
```

## 📚 相关文档

- [README.md](README.md) - 插件详细介绍


## 🆘 获取帮助

如果遇到问题：
1. 查看插件日志文件
2. 启用调试模式：`debug_mode = true`
3. 运行测试脚本：`python test_plugin.py`
4. 检查 MaiBot 主程序日志

## ✅ 安装检查清单

- [ ] 插件文件已放置在正确位置
- [ ] 依赖包已安装 (feedparser, aiofiles)
- [ ] 配置文件已正确设置
- [ ] MaiBot 重启后插件正常加载
- [ ] 命令 `/topic_config` 显示正确信息
- [ ] 命令 `/topic_test` 能生成话题

完成以上检查后，插件就可以正常工作了！🎉
