"""首次会话 onboarding：以 agents.md 为状态机账本的引导系统.

契约（三态编码）：
- 格式：`## 用户档案` 段内 `- 字段名：值`（与 config._parse_md 同构）
- 行缺失（段在、字段行不在）→ 物理截断/手动删除 → 状态 IN_PROGRESS，续问该字段
- 行存在、值为 `（未填）` 占位符 → 用户主动跳过 → 合法完成态，不追问
- 行存在、值非空 → 已填写
- 硬必填 = 称呼（占位也算未完成，强制续问）；软必填 = 其余项（缺失续问、可再跳过）
- 解析按字段名匹配，不依赖行顺序；写回为整文件原子重建

数据主权（M33 前瞻）：档案整体属 B_out 外层（模型可见行为基线），
采集时明示注入系统提示词；敏感项引导模糊填写，私有内容走 memory/（PrivateCore 侧）。
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# 占位符：用户主动跳过的标记（区别于「行缺失」的截断态）
UNFILLED = "（未填）"
# 硬必填字段：缺失/占位均判定未完成
HARD_REQUIRED = "称呼"
# 敏感项：采集时提示可跳过（B_out 外层可见，避免身份/能力边界暴露）
SENSITIVE_FIELDS = {"技能", "编程熟悉度", "领域"}

# 提问项：key, 问题, 示例（顺序即断点续引导的遍历顺序）
ONBOARDING_QUESTIONS: list[tuple[str, str, str]] = [
    ("称呼", "你希望我怎么称呼你？", "例：Wayne / 王老师 / 随便叫"),
    ("人格", "你希望我以什么性格、语气与你相处？", "例：沉稳直白 / 轻松随意 / 严谨专业"),
    ("技能", "你擅长什么？平时主要做什么？", "例：写代码 / 做产品 / 研究历史 / 什么都干"),
    ("编程熟悉度", "你了解编程、代码吗？", "例：完全不懂 / 略懂 / 熟练写代码"),
    ("大白话", "解释问题时，需要我用大白话讲，还是可以用专业术语？", "例：大白话 / 术语可以 / 两者结合"),
    ("领域", "你关注或工作的领域是什么？", "例：AI 架构 / 商业分析 / 教育 / 无特别领域"),
]

STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETE = "COMPLETE"

_PROFILE_SECTION_RE = re.compile(r"^##\s+用户档案\s*$", re.MULTILINE)
_SECTION_BODY_RE = re.compile(
    r"^##\s+用户档案\s*\n(.*?)(?=\n##\s+|\Z)", re.DOTALL | re.MULTILINE
)
_ITEM_RE = re.compile(r"^-\s*([^：:]+)[：:]\s*(.*)$")


@dataclass
class UserProfile:
    """用户档案（answers 仅含已填写的非占位字段）."""

    answers: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.answers)

    def to_summary(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.answers.items())


def _extract_section(text: str) -> str:
    m = _SECTION_BODY_RE.search(text)
    return m.group(1) if m else ""


def _parse_items(section: str) -> dict[str, str]:
    """把段落解析为 {字段名: 值}；仅收集非占位非空行."""
    items: dict[str, str] = {}
    for line in section.splitlines():
        m = _ITEM_RE.match(line.strip())
        if not m:
            continue
        key, value = m.group(1).strip(), m.group(2).strip()
        if value and value != UNFILLED:
            items[key] = value
    return items


def _present_keys(section: str) -> set[str]:
    """段内出现的字段行集合（无论占位与否）."""
    return {m.group(1).strip() for line in section.splitlines() if (m := _ITEM_RE.match(line.strip()))}


def parse_profile(global_agents_md: Path) -> tuple[UserProfile, str]:
    """读取 agents.md，判定档案进度状态（唯一进度账本，不依赖外部布尔标记）.

    返回 (档案, 状态)：NOT_STARTED / IN_PROGRESS / COMPLETE
    """
    if not global_agents_md.is_file():
        return UserProfile(), STATUS_NOT_STARTED
    text = global_agents_md.read_text(encoding="utf-8")
    if not _PROFILE_SECTION_RE.search(text):
        return UserProfile(), STATUS_NOT_STARTED

    section = _extract_section(text)
    items = _parse_items(section)
    present = _present_keys(section)

    # 硬必填：称呼行缺失或占位 → 未完成
    if HARD_REQUIRED not in present or not items.get(HARD_REQUIRED):
        return UserProfile(items), STATUS_IN_PROGRESS

    # 软必填：字段行缺失（截断）→ 未完成；占位或已填 → 完成
    missing = [k for k, *_ in ONBOARDING_QUESTIONS if k not in present]
    if missing:
        return UserProfile(items), STATUS_IN_PROGRESS

    return UserProfile(items), STATUS_COMPLETE


def collect_profile(
    input_fn=input, existing: UserProfile | None = None, force: bool = False
) -> UserProfile:
    """交互式采集用户档案（支持断点续引导）.

    - existing: 已填字段（续问时跳过）
    - force: True 时全量重问（--restart-onboard）
    """
    existing = existing or UserProfile()
    profile = UserProfile(dict(existing.answers))
    questions = ONBOARDING_QUESTIONS if force else [
        (k, q, e) for k, q, e in ONBOARDING_QUESTIONS if k not in profile.answers
    ]
    if not questions:
        return profile

    head = "\n[首次启动] 为了更好地配合你，先问你几个问题（每项直接回车可跳过）："
    if existing.answers:
        head = f"\n[续填用户档案] 已记录 {len(existing.answers)} 项，剩余 {len(questions)} 项："
    print(head)
    print("（此档案会注入系统提示词供模型参考；敏感项可不填，私有内容请走 memory/）")

    for key, question, example in questions:
        prompt = f"\n? {question}\n  {example}"
        if key in SENSITIVE_FIELDS:
            prompt += "\n  （敏感项，介意可不填）"
        try:
            ans = input_fn(prompt + "\n  你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans:
            profile.answers[key] = ans
    return profile


def _render_block(answers: dict[str, str]) -> str:
    """渲染用户档案段落：每个字段一行，未填/跳过写占位符."""
    lines = [
        "## 用户档案",
        "",
        "> 由首次启动 onboarding 自动记录，可随时编辑。",
        "> 该档案会注入系统提示词供模型参考；敏感信息请勿填写真实值。",
    ]
    for key, *_ in ONBOARDING_QUESTIONS:
        value = answers.get(key, "")
        lines.append(f"- {key}：{value or UNFILLED}")
    return "\n".join(lines)


def write_profile(global_agents_md: Path, profile: UserProfile) -> Path:
    """把用户档案写入 global/agents.md，原子重建段落（保留其余配置）.

    原子写回：写临时文件 → os.replace 重命名，避免写到一半崩溃截断文件。
    """
    global_agents_md.parent.mkdir(parents=True, exist_ok=True)
    if not global_agents_md.is_file():
        global_agents_md.write_text("# 全局常项配置（global/agents.md）\n", encoding="utf-8")

    block = _render_block(profile.answers)
    text = global_agents_md.read_text(encoding="utf-8")
    if _PROFILE_SECTION_RE.search(text):
        text = _SECTION_BODY_RE.sub(lambda _: block, text)
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"

    fd, tmp_path = tempfile.mkstemp(
        dir=str(global_agents_md.parent), prefix=".agents", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, global_agents_md)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return global_agents_md