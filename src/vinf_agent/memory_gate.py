"""记忆读写门（B_in 隔离层）.

私人记忆（memory/ 目录）是内核 PrivateCore，外部输入不得直接覆盖。
本模块统一接管 memory 的读写：写入前做价值判断钩子，外部数据只能经工具显式写入。
"""
from __future__ import annotations

from pathlib import Path


class MemoryGate:
    """B_in 记忆读写门：私人记忆唯一入口."""

    def __init__(self, memory_dir: Path, value_judge=None):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        # value_judge(text) -> bool，决定该信息是否值得永久保存（默认全部保存）
        self.value_judge = value_judge or (lambda text: True)

    def read(self) -> str:
        """读取全部私人记忆（只读，不改动）."""
        chunks = []
        for f in sorted(self.memory_dir.glob("*.md")):
            chunks.append(f"## {f.stem}\n{f.read_text(encoding='utf-8')}")
        return "\n\n".join(chunks)

    def write(self, title: str, text: str) -> Path:
        """写入一条私人记忆（B_in 隔离：仅本模块可写 memory/）."""
        if not self.value_judge(text):
            raise ValueError("记忆价值判断未通过，拒绝沉淀")
        safe_title = "".join(c for c in title if c.isalnum() or c in "_-").strip()
        if not safe_title:
            safe_title = "note"
        path = self.memory_dir / f"{safe_title}.md"
        path.write_text(text, encoding="utf-8")
        return path