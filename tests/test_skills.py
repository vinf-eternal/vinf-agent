"""skills.py 加载系统测试."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from vinf_agent.skills import (  # noqa: E402
    load_skill_from_file,
    load_skills,
    parse_frontmatter,
    render_skills_block,
)


def _make_skill_dir(tmp_path: Path, name: str, desc: str, body: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n{body}", encoding="utf-8"
    )
    return d


def test_parse_frontmatter():
    meta, body = parse_frontmatter("---\nname: foo\ndescription: bar\n---\n\nhello")
    assert meta == {"name": "foo", "description": "bar"}
    assert body == "hello"


def test_parse_frontmatter_no_marker():
    meta, body = parse_frontmatter("plain text")
    assert meta == {}
    assert body == "plain text"


def test_load_skill_from_file_requires_description(tmp_path):
    no_desc = tmp_path / "nod.md"
    no_desc.write_text("---\nname: x\n---\nbody", encoding="utf-8")
    assert load_skill_from_file(no_desc) is None

    with_desc = tmp_path / "desc.md"
    with_desc.write_text(
        "---\nname: y\ndescription: has desc\n---\nbody", encoding="utf-8"
    )
    s = load_skill_from_file(with_desc)
    assert s is not None and s.name == "y"


def test_load_skills_recursive(tmp_path):
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    _make_skill_dir(skill_dir, "socrates", "产婆术", "追问")
    _make_skill_dir(skill_dir, "caocao", "务实决断", "目标优先")

    result = load_skills(skill_dir)
    names = sorted(s.name for s in result.skills)
    assert names == ["caocao", "socrates"]


def test_load_skills_disabled_flag(tmp_path):
    d = tmp_path / "off"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: off\ndescription: 禁用 skill\nenable: false\n---\n\nbody",
        encoding="utf-8",
    )
    result = load_skills(d)
    assert len(result.skills) == 1
    assert result.skills[0].enabled is False


def test_render_skills_block_only_enabled(tmp_path):
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    _make_skill_dir(skill_dir, "socrates", "产婆术", "追问")
    result = load_skills(skill_dir)
    block = render_skills_block(result.skills)
    assert "<skill name=\"socrates\">" in block
    assert "产婆术" in block


def test_load_skills_missing_dir(tmp_path):
    result = load_skills(tmp_path / "nope")
    assert result.skills == []
    assert result.diagnostics