"""工具注册与执行测试."""
from vinf_agent.memory_gate import MemoryGate
from vinf_agent.tools import ToolRegistry, build_tools


def _gate(tmp_path):
    return MemoryGate(tmp_path / "memory")


def test_build_tools(tmp_path):
    reg = build_tools(_gate(tmp_path))
    assert set(reg.names()) == {"memory_write", "memory_read", "exit_session"}
    assert len(reg.schemas()) == 3


def test_memory_write_tool(tmp_path):
    reg = build_tools(_gate(tmp_path))
    r = reg.get("memory_write").fn({"title": "t", "text": "值得保存的信息"})
    assert r.ok and "已保存" in r.output


def test_memory_write_rejected(tmp_path):
    gate = MemoryGate(tmp_path / "memory", value_judge=lambda t: len(t) > 50)
    reg = build_tools(gate)
    r = reg.get("memory_write").fn({"title": "t", "text": "短"})
    assert not r.ok and "价值判断" in r.error


def test_exit_session_terminates(tmp_path):
    reg = build_tools(_gate(tmp_path))
    r = reg.get("exit_session").fn({})
    assert r.ok and r.terminate


def test_unknown_tool(tmp_path):
    reg = build_tools(_gate(tmp_path))
    assert reg.get("nonexistent") is None