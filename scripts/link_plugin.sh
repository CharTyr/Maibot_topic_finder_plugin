#!/usr/bin/env bash
set -euxo pipefail

: "${HOST_APP_DIR:?HOST_APP_DIR not set}"
: "${PLUGIN_DIR:?PLUGIN_DIR not set}"

# 插件名默认是 Maibot_topic_finder_plugin
PLUGIN_NAME="${PLUGIN_NAME:-Maibot_topic_finder_plugin}"

# 目标放到 MaiBot 的 plugins/ 下
mkdir -p "$HOST_APP_DIR/plugins"
TARGET="$HOST_APP_DIR/plugins/$PLUGIN_NAME"

# 软链接（也可改为复制）
rm -rf "$TARGET"
ln -s "$PLUGIN_DIR" "$TARGET"

echo "Linked $PLUGIN_DIR -> $TARGET"