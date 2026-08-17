"""onboarding.py 测试：状态机契约三态 + 断点续引导 + 原子写回."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from vinf_agent.onboarding import (  # noqa: E402
    ONBOARDING_QUESTIONS,
    STATUS_COMPLETE,
    STATUS_IN_PROGRESS,
    STATUS_NOT_STARTED,
    UserProfile,
    collect_profile,
    parse_profile,
    write_profile,
)


def _full_md(tmp_path: Path, override: str = "") -> Path:
    md = tmp_path / "global" / "agents.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "# 全局配置\n\n## 用户档案\n\n> 自动记录\n\n"
        "- 称呼：Wayne\n- 人格：直白\n- 技能：写代码\n"
        "- 编程熟悉度：熟练\n- 大白话：大白话\n- 领域：AI 架构\n"
        + override,
        encoding="utf-8",
    )
    return md


# ---- 三态判定（parse_profile） ----


def test_not_started_when_no_section(tmp_path):
    md = tmp_path / "global" / "agents.md"
    md.parent.mkdir(parents=True)
    md.write_text("# x\n", encoding="utf-8")
    profile, status = parse_profile(md)
    assert status == STATUS_NOT_STARTED
    assert not profile.answers


def test_not_started_when_missing_file(tmp_path):
    profile, status = parse_profile(tmp_path / "nope" / "agents.md")
    assert status == STATUS_NOT_STARTED


def test_complete_when_all_filled(tmp_path):
    md = _full_md(tmp_path)
    profile, status = parse_profile(md)
    assert status == STATUS_COMPLETE
    assert profile.answers["称呼"] == "Wayne"


def test_in_progress_when_missing_field(tmp_path):
    md = _full_md(tmp_path)
    # 手动删除「领域」行 → 截断态
    text = md.read_text(encoding="utf-8").replace("- 领域：AI 架构\n", "")
    md.write_text(text, encoding="utf-8")
    _, status = parse_profile(md)
    assert status == STATUS_IN_PROGRESS


def test_complete_when_placeholder_skip(tmp_path):
    md = _full_md(tmp_path)
    # 用户主动跳过「技能」→ 占位符 → 完成态，不追问
    text = md.read_text(encoding="utf-8").replace("- 技能：写代码\n", "- 技能：（未填）\n")
    md.write_text(text, encoding="utf-8")
    profile, status = parse_profile(md)
    assert status == STATUS_COMPLETE
    assert "技能" not in profile.answers


def test_in_progress_when_hard_required_placeholder(tmp_path):
    md = _full_md(tmp_path)
    # 硬必填「称呼」占位 → 未完成
    text = md.read_text(encoding="utf-8").replace("- 称呼：Wayne\n", "- 称呼：（未填）\n")
    md.write_text(text, encoding="utf-8")
    _, status = parse_profile(md)
    assert status == STATUS_IN_PROGRESS


# ---- 断点续引导（collect_profile + existing） ----


def test_collect_resume_skips_filled(tmp_path):
    md = _full_md(tmp_path)
    existing, _ = parse_profile(md)
    # 模拟只缺「领域」→ 续问只问缺失项
    existing.answers.pop("领域", None)
    answers = iter(["商业分析"])
    profile = collect_profile(input_fn=lambda _p: next(answers), existing=existing)
    assert profile.answers["称呼"] == "Wayne"
    assert profile.answers["领域"] == "商业分析"


def test_collect_force_reasks_all():
    answers = iter(["W2", "P2", "S2", "C2", "B2", "D2"])
    profile = collect_profile(input_fn=lambda _p: next(answers), force=True)
    assert len(profile.answers) == len(ONBOARDING_QUESTIONS)
    assert profile.answers["称呼"] == "W2"


def test_collect_skips_empty_input():
    answers = iter(["Wayne", "", "略懂", "", "大白话", ""])
    profile = collect_profile(input_fn=lambda _p: next(answers))
    assert "称呼" in profile.answers
    assert "人格" not in profile.answers
    assert "大白话" in profile.answers


def test_profile_summary():
    p = UserProfile({"称呼": "W", "人格": "P"})
    assert "称呼=W" in p.to_summary()


# ---- 写回 ----


def test_write_preserves_existing_config(tmp_path):
    md = _full_md(tmp_path, override="")
    write_profile(md, UserProfile({"称呼": "Wayne", "领域": "AI 架构"}))
    text = md.read_text(encoding="utf-8")
    assert "## 人设" in text or "全局配置" in text
    assert "用户档案" in text
    assert "称呼：Wayne" in text
    assert "领域：AI 架构" in text


def test_write_replaces_section_only(tmp_path):
    md = tmp_path / "global" / "agents.md"
    md.parent.mkdir(parents=True)
    md.write_text("# x\n\n## 用户档案\n\n- 称呼：旧\n", encoding="utf-8")
    write_profile(md, UserProfile({"称呼": "新"}))
    text = md.read_text(encoding="utf-8")
    assert "称呼：新" in text
    assert "称呼：旧" not in text
    assert "# x" in text


def test_write_is_atomic_no_tmp_left(tmp_path):
    md = tmp_path / "global" / "agents.md"
    md.parent.mkdir(parents=True)
    write_profile(md, UserProfile({"称呼": "W"}))
    leftovers = list(tmp_path.glob("global/.agents*.tmp"))
    assert leftovers == []
    assert md.is_file()