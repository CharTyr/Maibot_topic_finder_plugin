#!/usr/bin/env bash
set -euxo pipefail

# -------- 配置 --------
PY="${PYTHON:-python3}"
HOST_DIR="${HOST_DIR:-host-maibot}"
HOST_REPO="${HOST_REPO:-https://github.com/MaiM-with-u/MaiBot}"
HOST_BRANCH="${HOST_BRANCH:-main}"
HOST_CACHE_DIR="${HOST_CACHE_DIR:-$(dirname "$0")/../host_cache/MaiBot}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -d "$HOST_CACHE_DIR" ]; then
  HOST_CACHE_DIR="$(cd "$HOST_CACHE_DIR" && pwd)"
fi

# -------- 1) 获取宿主 MaiBot --------
if [ ! -d "$HOST_DIR" ]; then
  if [ -d "$HOST_CACHE_DIR" ]; then
    echo "Using offline MaiBot cache from $HOST_CACHE_DIR"
    cp -R "$HOST_CACHE_DIR" "$HOST_DIR"
    # 初始化测试分支
    if [ ! -d "$HOST_DIR/.git" ]; then
      (
        cd "$HOST_DIR"
        git init
        git checkout -b offline-test-host
        git config user.email "offline@example.com"
        git config user.name "Offline Tester"
        git add .
        git commit -m "Initialize offline host stub"
      ) || true
    fi
  else
    git clone --depth=1 --branch "$HOST_BRANCH" "$HOST_REPO" "$HOST_DIR"
  fi
fi

# -------- 2) 创建虚拟环境并安装 MaiBot 依赖 --------
cd "$HOST_DIR"
$PY -m venv .venv
source .venv/bin/activate

if [ -f requirements.txt ] && [ -s requirements.txt ]; then
  pip install -r requirements.txt
fi
if [ -f pyproject.toml ]; then
  pip install -e . || true
fi

# -------- 3) 连接插件到 MaiBot 的 plugins/ --------
cd "$ROOT_DIR"
export HOST_APP_DIR="$PWD/$HOST_DIR"
export PLUGIN_DIR="$PWD"
export PLUGIN_NAME="Maibot_topic_finder_plugin"
bash scripts/link_plugin.sh

export PYTHONPATH="$HOST_APP_DIR:${PYTHONPATH:-}"

# -------- 4) 运行测试 --------
if command -v pytest >/dev/null 2>&1; then
  pytest -q
elif [ -f Makefile ]; then
  make test
else
  echo "No tests configured. Please add pytest or a Makefile target."
  exit 1
fi
