#!/usr/bin/env python3
"""零安装入口：python run.py [--web] [--port 8787]

不需要 pip install。纯 stdlib，直接把 src/ 加入 sys.path 后启动。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from vinf_agent.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())