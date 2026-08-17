"""双层循环（外环交互 + 内环工具）测试.

使用可控 FakeLLM 驱动 AgentLoop，覆盖：
- 简单回复（无工具调用）
- 工具调用 → 执行 → 回填 → 再生成
- length-stop 防残缺执行（全部 fail，不执行）
- terminate 强制终止内环
- error/aborted 终止会话
- 外环 steering（input_provider 返回多条输入）
- B_out 外层过滤生效
- 会话起始注入私人记忆
"""
import pytest

from vinf_agent.agent_loop import AgentLoop, Event
from vinf_agent.filter import OuterFilter
from vinf_agent.llm import LLMResponse, ToolCall
from vinf_agent.memory_gate import MemoryGate
from vinf_agent.tools import build_tools


class FakeLLM:
    """脚本化 LLM：按序列返回预设回复."""

    def __init__(self, responses: list[LLMResponse]):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def call(self, messages: list[dict]) -> LLMResponse:
        self.calls.append(messages)
        return self.responses.pop(0)


def _mk_call(name, args, cid="call_1"):
    return ToolCall(id=cid, name=name, arguments=args)


def _make_loop(tmp_path, llm, filter_words=None, value_judge=None):
    gate = MemoryGate(tmp_path / "memory", value_judge=value_judge)
    tools = build_tools(gate)
    events: list[Event] = []
    loop = AgentLoop(
        llm=llm,
        tools=tools,
        gate=gate,
        outer_filter=OuterFilter(max_len=1000, sensitive_words=filter_words or []),
        system_prompt="测试系统提示词",
        on_event=events.append,
    )
    return loop, gate, events


def _session(loop, inputs):
    return list(loop.run_session(lambda: (inputs.pop(0) if inputs else None)))


def test_simple_reply(tmp_path):
    loop, _, events = _make_loop(
        tmp_path, FakeLLM([LLMResponse(content="你好！")])
    )
    resp = loop.run_turn("hi")
    assert resp.content == "你好！"
    types = [e.type for e in events]
    assert types[:3] == ["turn_start", "message_start", "message_end"]
    assert types[-1] == "turn_end"


def test_tool_call_flow(tmp_path):
    """模型先请求 memory_write，工具执行回填后再生成."""
    llm = FakeLLM(
        [
            LLMResponse(
                content="",
                stop_reason="tool_use",
                tool_calls=[_mk_call("memory_write", {"title": "t", "text": "数据"})],
            ),
            LLMResponse(content="已保存"),
        ]
    )
    loop, gate, _ = _make_loop(tmp_path, llm)
    resp = loop.run_turn("保存这个")
    assert resp.content == "已保存"
    assert "数据" in gate.read()
    # 第二次 LLM 调用应包含 tool 回填消息
    assert any(m["role"] == "tool" for m in llm.calls[1])


def test_length_stop_fails_all(tmp_path):
    """stop_reason==length → 工具全部失败，不执行."""
    executed = []

    class Tracked(LLMResponse):
        pass

    llm = FakeLLM(
        [
            LLMResponse(
                content="",
                stop_reason="length",
                tool_calls=[
                    _mk_call("memory_write", {"title": "a", "text": "x"}, cid="c1"),
                    _mk_call("exit_session", {}, cid="c2"),
                ],
            ),
            LLMResponse(content="收尾"),
        ]
    )
    loop, gate, events = _make_loop(tmp_path, llm)
    resp = loop.run_turn("写记忆")
    assert resp.content == "收尾"
    assert gate.read() == ""  # memory_write 未执行
    results = [e for e in events if e.type == "tool_result"]
    assert all(e.data["ok"] is False for e in results)
    assert all(e.data["error"] == "truncated_args" for e in results)


def test_terminate_stops_inner_loop(tmp_path):
    """exit_session 返回 terminate → 即使后续回复含工具也不再执行."""
    llm = FakeLLM(
        [
            LLMResponse(
                content="",
                stop_reason="tool_use",
                tool_calls=[_mk_call("exit_session", {}, cid="c1")],
            ),
            LLMResponse(
                content="",
                stop_reason="tool_use",
                tool_calls=[_mk_call("memory_write", {"title": "a", "text": "不应写入"}, cid="c2")],
            ),
        ]
    )
    loop, gate, _ = _make_loop(tmp_path, llm)
    resp = loop.run_turn("退出")
    assert gate.read() == ""  # 第二个工具调用未执行
    assert resp.content == ""


def test_steering_session(tmp_path):
    """外环：多条输入依次处理，None 结束会话."""
    llm = FakeLLM([LLMResponse(content="答1"), LLMResponse(content="答2")])
    loop, _, _ = _make_loop(tmp_path, llm)
    responses = _session(loop, ["q1", "q2"])
    assert [r.content for r in responses] == ["答1", "答2"]
    assert len(llm.calls) == 2


def test_error_terminates_session(tmp_path):
    llm = FakeLLM(
        [
            LLMResponse(content="ok"),
            LLMResponse(content="", stop_reason="error"),
        ]
    )
    loop, _, _ = _make_loop(tmp_path, llm)
    responses = _session(loop, ["q1", "q2", "q3"])
    assert len(responses) == 2  # q3 未处理，会话结束


def test_outer_filter_applied(tmp_path):
    """B_out：敏感词在进入 LLM 前被过滤."""
    llm = FakeLLM([LLMResponse(content="收到")])
    loop, _, _ = _make_loop(tmp_path, llm, filter_words=["禁词"])
    loop.run_turn("这里有个禁词")
    last_user = [m for m in llm.calls[0] if m["role"] == "user"][-1]
    assert "禁词" not in last_user["content"]


def test_memory_injected_at_session_start(tmp_path):
    """会话起始注入私人记忆（B_in 只读注入上下文）. """
    gate = MemoryGate(tmp_path / "memory")
    gate.write("seed", "预置记忆内容")
    llm = FakeLLM([LLMResponse(content="已读")])
    loop, _, _ = _make_loop(tmp_path, llm)
    _session(loop, ["hi"])
    system_msgs = [m for m in llm.calls[0] if m["role"] == "system"]
    assert any("预置记忆内容" in m["content"] for m in system_msgs)


def test_max_inner_iterations(tmp_path):
    """内环迭代上限保护，防止无限工具循环."""
    llm = FakeLLM([])

    def always_tool_call(messages):
        return LLMResponse(
            content="",
            stop_reason="tool_use",
            tool_calls=[_mk_call("memory_read", {}, cid="c1")],
        )

    # 用脚本伪造超过上限的工具调用序列
    llm.call = always_tool_call
    loop, _, _ = _make_loop(tmp_path, llm)
    loop.max_inner_iterations = 3
    resp = loop.run_turn("循环")
    assert resp.content == ""  # 被迭代上限打断