#!/usr/bin/env bash
set -euxo pipefail

# -------- 配置 --------
PY="${PYTHON:-python3}"
HOST_DIR="${HOST_DIR:-host-maibot}"
HOST_REPO="${HOST_REPO:-https://github.com/MaiM-with-u/MaiBot}"
HOST_BRANCH="${HOST_BRANCH:-main}"

# -------- 1) 获取宿主 MaiBot --------
if [ ! -d "$HOST_DIR/.git" ]; then
  git clone --depth=1 --branch "$HOST_BRANCH" "$HOST_REPO" "$HOST_DIR"
fi

# -------- 2) 创建虚拟环境并安装 MaiBot 依赖 --------
cd "$HOST_DIR"
$PY -m venv .venv
source .venv/bin/activate

# MaiBot 使用 Python，仓库提供了 requirements/pyproject（以官方仓库为准）
# 优先使用 uv/lock 文件或 requirements.txt/pyproject.toml
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
fi
if [ -f pyproject.toml ]; then
  pip install -e .
fi

# -------- 3) 链接你的插件到 MaiBot 的 plugins/ --------
cd ..
export HOST_APP_DIR="$PWD/$HOST_DIR"
export PLUGIN_DIR="$PWD"
export PLUGIN_NAME="Maibot_topic_finder_plugin"
bash scripts/link_plugin.sh

# -------- 4) 运行测试（示例用 pytest；也可替换为你的测试命令）--------
if command -v pytest >/dev/null 2>&1; then
  pytest -q
elif [ -f Makefile ]; then
  make test
else
  echo "No tests configured. Please add pytest or a Makefile target."
  exit 1
fi