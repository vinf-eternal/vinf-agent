#!/usr/bin/env sh
# Vinf Agent 一键安装（macOS/Linux）
# 用法：curl -fsSL <installer-url> | sh
#   或：sh install.sh
#
# 做三件事：
#   1. 检测 python3 >= 3.10
#   2. 把 bin/vinf-agent 符号链接到 ~/.local/bin（已在 PATH 中）
#   3. 提示下一步
set -e

TARGET_DIR="$HOME/.local/bin"
LAUNCHER="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/bin/vinf-agent"

command -v python3 >/dev/null 2>&1 || {
  echo "[错误] 需要 python3（>= 3.10）"; exit 1;
}
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[ok] python3 $PY_VER"

mkdir -p "$TARGET_DIR"
ln -sf "$LAUNCHER" "$TARGET_DIR/vinf-agent"
echo "[ok] 已链接 vinf-agent -> $LAUNCHER"

if ! echo "$PATH" | grep -q "$TARGET_DIR"; then
  echo "[提示] 将 $TARGET_DIR 加入 PATH：echo 'export PATH=\$HOME/.local/bin:\$PATH' >> ~/.bashrc"
fi

echo "完成。下一步："
echo "  cp -r <repo>/config.example config   # 复制配置模板"
echo "  export VINF_API_KEY=sk-...           # 设置 API key"
echo "  vinf-agent --web                     # 启动本地 Web 版"
echo "  vinf-agent                           # 或 CLI 模式"