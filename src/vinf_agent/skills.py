"""Skill 加载系统（对齐 pi 的 SKILL.md + frontmatter 机制，零依赖版）.

- 每个 skill = 一个目录下的 SKILL.md（或根目录直接放 .md 文件带 frontmatter）
- frontmatter: name / description / enable 等
- 加载后注入系统提示词 <skill_injection> 块
- 开源版为 B_out 配置层，仅注入文本规则，不执行任意代码
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    """一个已加载的 skill."""

    name: str
    description: str
    content: str
    file_path: str
    enabled: bool = True

    def render(self) -> str:
        """渲染为注入系统提示词的块."""
        return (
            f"<skill name=\"{self.name}\">\n{self.content}\n</skill>"
        )


@dataclass
class SkillLoadResult:
    """skill 目录加载结果."""

    skills: list[Skill] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_KEY_VALUE_RE = re.compile(r"^\s*([a-zA-Z0-9_-]+)\s*:\s*(.*?)\s*$", re.MULTILINE)


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """解析 YAML 风格 frontmatter（仅支持 k: v 简单键值，零依赖）. Returns (meta, body)."""
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content
    raw = m.group(1)
    body = content[m.end() :].strip()
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        kv = _KEY_VALUE_RE.match(line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip("\"'")
    return meta, body


def load_skill_from_file(path: Path) -> Skill | None:
    """从单个文件加载 skill（要求有 description，否则视为普通文档跳过）."""
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)
    description = meta.get("description", "")
    if not description:
        return None
    name = meta.get("name", path.parent.name if path.name == "SKILL.md" else path.stem)
    return Skill(
        name=name,
        description=description,
        content=body,
        file_path=str(path),
        enabled=meta.get("enable", "true").lower() != "false",
    )


def load_skills(skill_dir: Path) -> SkillLoadResult:
    """从目录递归加载所有 skill.

    规则（对齐 pi）：
    - 每个子目录下的 SKILL.md 是一个 skill
    - 目录根下的 .md 文件若带 description frontmatter 也算 skill
    - 跳过 .开头目录与 __pycache__ 等
    """
    result = SkillLoadResult()
    if not skill_dir.is_dir():
        result.diagnostics.append(f"skill 目录不存在：{skill_dir}")
        return result

    # 1. 根目录下的 SKILL.md
    root_skill = skill_dir / "SKILL.md"
    if root_skill.is_file():
        s = load_skill_from_file(root_skill)
        if s:
            result.skills.append(s)

    # 2. 递归子目录
    for child in sorted(skill_dir.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            skill_file = child / "SKILL.md"
            if skill_file.is_file():
                s = load_skill_from_file(skill_file)
                if s:
                    result.skills.append(s)
            continue
        # 3. 根目录下带 frontmatter 的 .md
        if child.suffix == ".md" and child.name != "SKILL.md":
            s = load_skill_from_file(child)
            if s:
                result.skills.append(s)

    return result


def render_skills_block(skills: list[Skill]) -> str:
    """渲染全部启用的 skill 为注入块."""
    enabled = [s for s in skills if s.enabled]
    if not enabled:
        return ""
    parts = []
    for s in enabled:
        parts.append(
            f"### Skill: {s.name}\n"
            f"描述: {s.description}\n\n"
            f"{s.render()}"
        )
    return "\n\n".join(parts)