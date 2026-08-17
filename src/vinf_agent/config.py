"""三层配置读取 + append_system 第四层热补丁（B_out 配置层）.

优先级：append_system.md > project/agents.md > global/agents.md。
所有配置文件均为 markdown，本模块仅提取结构化段落，不执行任意代码。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AgentConfig:
    """解析后的配置对象."""

    persona: str = ""
    memory_rules: list[str] = field(default_factory=list)
    behavior_boundaries: list[str] = field(default_factory=list)
    project_context: dict[str, str] = field(default_factory=dict)
    project_rules: list[str] = field(default_factory=list)
    appendix: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def merge(self, other: "AgentConfig") -> None:
        """用更高优先级配置覆盖当前配置（append > project > global）."""
        if other.persona:
            self.persona = other.persona
        if other.memory_rules:
            self.memory_rules = other.memory_rules
        if other.behavior_boundaries:
            self.behavior_boundaries = other.behavior_boundaries
        if other.project_context:
            self.project_context.update(other.project_context)
        if other.project_rules:
            self.project_rules = other.project_rules
        if other.appendix:
            self.appendix = other.appendix
        self.sources.extend(other.sources)

    def to_summary(self) -> str:
        """生成注入系统提示词的摘要."""
        lines = []
        if self.persona:
            lines.append(f"人设: {self.persona}")
        if self.memory_rules:
            lines.append("记忆规则: " + "; ".join(self.memory_rules))
        if self.behavior_boundaries:
            lines.append("行为边界: " + "; ".join(self.behavior_boundaries))
        if self.project_context:
            lines.append(
                "项目上下文: " + "; ".join(f"{k}={v}" for k, v in self.project_context.items())
            )
        if self.project_rules:
            lines.append("项目规则: " + "; ".join(self.project_rules))
        if self.appendix:
            lines.append("热补丁: " + "; ".join(self.appendix))
        return "\n".join(lines)


_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _parse_section_name(name: str) -> str:
    return name.strip().strip("`").lower()


def _parse_md(path: Path) -> AgentConfig:
    """解析单个 markdown 配置文件为 AgentConfig."""
    cfg = AgentConfig(sources=[str(path)])
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            current = _parse_section_name(m.group(1))
            sections.setdefault(current, [])
            continue
        if current:
            stripped = line.strip()
            if stripped and not stripped.startswith(">"):
                sections[current].append(stripped)

    def _bullets(name: str) -> list[str]:
        out = []
        for b in sections.get(name, []):
            stripped = b
            if stripped.startswith("-"):
                stripped = stripped[1:]
            elif re.match(r"^\d+[\.、]", stripped):
                stripped = re.sub(r"^\d+[\.、]\s*", "", stripped)
            stripped = stripped.strip()
            if stripped:
                out.append(stripped)
        return out

    cfg.persona = "\n".join(_bullets("人设")) or "\n".join(_bullets("persona"))
    cfg.memory_rules = _bullets("记忆规则") or _bullets("memory rules")
    cfg.behavior_boundaries = _bullets("行为边界") or _bullets(
        "behavior boundaries"
    )
    for key in ("项目上下文", "project context"):
        for line in sections.get(key, []):
            if "：" in line or ":" in line:
                k, sep, v = line.partition("：" if "：" in line else ":")
                k = k.lstrip("-").strip()
                cfg.project_context[k] = v.strip()
    cfg.project_rules = _bullets("项目级规则") or _bullets("project rules")
    cfg.appendix = [l.lstrip("-").strip() for l in sections.get("临时规则", []) if l.startswith("-")]
    return cfg


class ConfigLoader:
    """按优先级链加载配置：global → project → append_system."""

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.global_path = self.config_dir / "global" / "agents.md"
        self.project_path = self.config_dir / "project" / "agents.md"
        self.appendix_path = self.config_dir / "append_system.md"

    def load(self) -> AgentConfig:
        merged = AgentConfig()
        if self.global_path.is_file():
            merged.merge(_parse_md(self.global_path))
        if self.project_path.is_file():
            merged.merge(_parse_md(self.project_path))
        if self.appendix_path.is_file():
            merged.merge(_parse_md(self.appendix_path))
        return merged

    @property
    def has_appendix(self) -> bool:
        return self.appendix_path.is_file()