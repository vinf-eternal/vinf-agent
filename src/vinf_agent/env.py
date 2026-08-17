"""轻量 .env 加载器（零依赖，对齐 python-dotenv 核心语义的 stdlib 实现）.

- 查找顺序：CLI 显式 `--env-file` > 当前目录 `.env` > 逐级父目录 `.env`
- 已存在的同名环境变量**不被覆盖**（真实环境优先级高于 .env 文件）
- 支持注释 `#`、双引号/单引号值、`export ` 前缀
- 加载结果仅注入内存 os.environ，永不写盘；API key 使用完即随进程结束丢弃
"""
from __future__ import annotations

import os
from pathlib import Path


def _parse_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        return None
    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip()
    if (len(value) >= 2 and value[0] == value[-1]) and value[0] in ("'", '"'):
        value = value[1:-1]
    elif value.startswith('"') or value.startswith("'"):
        value = value.strip(value[0])
    return key, value


def load_dotenv(explicit: str | None = None, start: Path | None = None) -> Path | None:
    """从 .env 文件加载环境变量到 os.environ（不覆盖已有变量）.

    返回实际加载的文件路径；未找到返回 None。
    """
    if explicit:
        target = Path(explicit)
        if not target.is_file():
            return None
    else:
        target = _find_dotenv(start or Path.cwd())
        if target is None:
            return None

    try:
        lines = target.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None

    for line in lines:
        parsed = _parse_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if key not in os.environ:
            os.environ[key] = value
    return target


def _find_dotenv(start: Path) -> Path | None:
    cur = start.resolve()
    while True:
        candidate = cur / ".env"
        if candidate.is_file():
            return candidate
        if cur.parent == cur:
            return None
        cur = cur.parent