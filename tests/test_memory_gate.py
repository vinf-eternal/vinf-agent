"""记忆读写门（B_in）测试."""
import pytest

from vinf_agent.memory_gate import MemoryGate


def test_write_and_read(tmp_path):
    gate = MemoryGate(tmp_path / "memory")
    path = gate.write("note1", "这是第一条记忆")
    assert path.is_file()
    assert "第一条记忆" in gate.read()


def test_value_judge_blocks_write(tmp_path):
    gate = MemoryGate(tmp_path / "memory", value_judge=lambda t: len(t) < 10)
    with pytest.raises(ValueError):
        gate.write("long", "这条记忆太长了不值得保存")
    assert gate.read() == ""


def test_safe_title(tmp_path):
    gate = MemoryGate(tmp_path / "memory")
    path = gate.write("重要 笔记/2026", "内容")
    assert "/" not in path.name


def test_read_empty(tmp_path):
    gate = MemoryGate(tmp_path / "memory")
    assert gate.read() == ""