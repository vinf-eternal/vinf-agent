"""外层过滤（B_out）.

用户输入在进入上下文前先经过外层过滤（PublicBuffer 校验）：
- 长度上限（防超长噪声）
- 敏感词过滤（可配置）
- 仅过滤输入，不触碰内核记忆（B_in 与 B_out 读写不互通）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OuterFilter:
    max_len: int = 20000
    sensitive_words: list[str] = field(default_factory=list)

    def filter(self, text: str) -> str:
        """返回清洗后的输入；超长截断，敏感词替换为 ***."""
        if len(text) > self.max_len:
            text = text[: self.max_len] + "\n[截断：输入超过上限]"
        for word in self.sensitive_words:
            text = text.replace(word, "***")
        return text

    def is_over_limit(self, text: str) -> bool:
        return len(text) > self.max_len