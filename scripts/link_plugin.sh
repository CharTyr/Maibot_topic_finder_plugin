#!/usr/bin/env bash
set -euxo pipefail

: "${HOST_APP_DIR:?HOST_APP_DIR not set}"
: "${PLUGIN_DIR:?PLUGIN_DIR not set}"

PLUGIN_NAME="${PLUGIN_NAME:-Maibot_topic_finder_plugin}"

mkdir -p "$HOST_APP_DIR/plugins"
TARGET="$HOST_APP_DIR/plugins/$PLUGIN_NAME"

rm -rf "$TARGET"
ln -s "$PLUGIN_DIR" "$TARGET"

echo "Linked $PLUGIN_DIR -> $TARGET"
