"""路由矩阵测试：声明式表 + 触发匹配 + 三注入位 + 工具门控 + sl0-mcp 接入."""
from __future__ import annotations

import json

import pytest

from vinf_agent.agent_loop import AgentLoop
from vinf_agent.llm import LLMClient, LLMResponse
from vinf_agent.memory_gate import MemoryGate
from vinf_agent.routing import (
    INJECT_PRE_TURN,
    INJECT_SYSTEM,
    INJECT_TOOL,
    MCPServer,
    Route,
    RoutingMatrix,
)
from vinf_agent.tools import Tool, ToolRegistry


# ---------- Route 触发匹配 ----------


def test_route_plain_substring():
    r = Route(trigger="周报", provider="skill", target="weekly_report")
    assert r.matches("帮我写周报")
    assert not r.matches("帮我写月报")


def test_route_kw_prefix():
    r = Route(trigger="kw:weekly report", provider="skill", target="weekly_report")
    assert r.matches("weekly report please")
    assert not r.matches("weeklyreportplease")


def test_route_regex():
    r = Route(trigger="re:如何|怎么|怎样", provider="skill", target="weekly_report")
    assert r.matches("请问怎么生成周报")
    assert r.matches("如何做")
    assert not r.matches("随便聊聊")


def test_route_tool_name():
    r = Route(trigger="tool:summon", provider="mcp", target="sl0-mcp")
    assert r.matches("任意消息", tool_name="summon")
    assert not r.matches("任意消息", tool_name="tick")
    assert not r.matches("任意消息")  # 无工具名上下文则不命中


def test_route_disabled():
    r = Route(trigger="周报", provider="skill", target="weekly_report", enabled=False)
    assert not r.matches("帮我写周报")


def test_route_bad_regex_returns_false():
    r = Route(trigger="re:[", provider="skill", target="weekly_report")
    assert not r.matches("anything")


# ---------- RoutingMatrix 命中 ----------


def _build_sample() -> RoutingMatrix:
    m = RoutingMatrix()
    m.add_route(Route(trigger="周报", provider="skill", target="weekly_report", priority=90))
    m.add_route(Route(trigger="summon|自省", provider="mcp", target="sl0-mcp", priority=80))
    m.add_route(Route(trigger="工具", provider="plugin", target="demo_plugin", priority=50, inject=INJECT_SYSTEM))
    m.add_route(Route(trigger="无人命中", provider="agent", target="caocao", priority=95, inject=INJECT_TOOL))
    m.add_route(Route(trigger="未知", provider="skill", target="ghost", priority=10))
    return m


def test_matrix_match_priority_order():
    m = _build_sample()
    hits = m.match("帮我写周报")
    assert [r.target for r in hits] == ["weekly_report"]


def test_matrix_multiple_hits_sorted_by_priority():
    m = _build_sample()
    m.add_route(Route(trigger="周报", provider="mcp", target="sl0-mcp", priority=100))
    hits = m.match("写周报")
    assert [r.target for r in hits] == ["sl0-mcp", "weekly_report"]


def test_matrix_no_hit():
    m = _build_sample()
    assert m.match("今天天气如何") == []


def test_matrix_system_routes_only():
    m = _build_sample()
    names = [r.target for r in m.system_routes()]
    assert names == ["demo_plugin"]
    assert "weekly_report" not in names


# ---------- 注入位渲染 ----------


def test_render_resolves_content():
    m = _build_sample()
    hits = m.match("帮我写周报")

    def resolver(route: Route) -> str:
        if route.target == "weekly_report":
            return "### 周报模板\n- 本周进展\n- 下周计划"
        return ""

    text = m.render(hits, resolver)
    assert "周报模板" in text
    assert "weekly_report" in text


def test_render_empty_when_no_content():
    m = _build_sample()
    hits = m.match("帮我写周报")
    text = m.render(hits, lambda r: "")
    assert text == ""


# ---------- 工具门控 ----------


def test_tool_gate_needs_binding():
    m = RoutingMatrix()
    m.add_route(Route(trigger="召唤", provider="mcp", target="sl0-mcp", inject=INJECT_TOOL))
    m.bind_server_tools("sl0-mcp", ["summon", "tick", "status"])
    # 未命中触发词 → 工具不激活
    assert m.routed_tool_names() == {"summon", "tick", "status"}
    assert m.active_tools("随便聊聊") == set()
    # 命中触发词 → 全部放行
    assert m.active_tools("召唤自指循环") == {"summon", "tick", "status"}


def test_tool_gate_without_binding_falls_back_to_target():
    m = RoutingMatrix()
    m.add_route(Route(trigger="召唤", provider="mcp", target="summon", inject=INJECT_TOOL))
    assert m.routed_tool_names() == {"summon"}
    assert m.active_tools("召唤") == {"summon"}
    assert m.active_tools("闲聊") == set()


# ---------- 矩阵加载 ----------


def test_load_from_dict():
    data = {
        "routes": [{"trigger": "周报", "provider": "skill", "target": "weekly_report"}],
        "mcp_servers": [{"name": "sl0-mcp", "command": "python", "args": ["-m", "x"]}],
    }
    m = RoutingMatrix.from_dict(data)
    assert len(m.routes) == 1
    assert m.routes[0].target == "weekly_report"
    assert m.mcp_servers[0].name == "sl0-mcp"
    assert m.mcp_servers[0].args == ["-m", "x"]


def test_load_missing_file_is_empty(tmp_path):
    m = RoutingMatrix.load(tmp_path / "nope.json")
    assert m.routes == []
    assert m.mcp_servers == []


def test_load_roundtrip_json(tmp_path):
    data = {
        "routes": [
            {"trigger": "周报|周计划", "provider": "skill", "target": "weekly_report", "priority": 90, "inject": INJECT_PRE_TURN}
        ],
        "mcp_servers": [{"name": "sl0-mcp", "command": "python", "args": []}],
    }
    p = tmp_path / "routes.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    m = RoutingMatrix.load(p)
    assert m.routes[0].trigger == "周报|周计划"
    assert m.routes[0].inject == INJECT_PRE_TURN
    assert m.routes[0].matches("帮我写周计划")


# ---------- AgentLoop 集成 ----------


class _FakeLLM(LLMClient):
    def __init__(self):
        self.saw_injections: list[str] = []
        self._tool_calls = []
        self._content = "done"

    def with_tool_calls(self, calls: list) -> "_FakeLLM":
        self._tool_calls = calls
        return self

    def call(self, messages: list[dict]) -> LLMResponse:
        for msg in messages:
            if msg.get("role") == "system" and "routing_injection" in msg.get("content", ""):
                self.saw_injections.append(msg["content"])
        # 有工具调用 → 第一轮返回工具，随后 mock 依据参数裁决
        if self._tool_calls:
            calls = self._tool_calls
            self._tool_calls = []
            return LLMResponse(content=self._content, stop_reason="tool_calls", tool_calls=calls)
        return LLMResponse(content=self._content, stop_reason="stop")


def _make_loop(router: RoutingMatrix, resolver) -> AgentLoop:
    llm = _FakeLLM()
    gate = MemoryGate.__new__(MemoryGate)  # 不落盘
    gate.read = lambda: ""
    registry = ToolRegistry()
    loop = AgentLoop(
        llm=llm,
        tools=registry,
        gate=gate,
        router=router,
        route_resolver=resolver,
    )
    return loop


def test_agent_loop_injects_route_on_hit():
    m = RoutingMatrix()
    m.add_route(Route(trigger="周报", provider="skill", target="weekly_report"))
    loop = _make_loop(m, lambda r: "### 周报模板\n- 进展")
    loop.run_turn("帮我写周报")
    assert loop.llm.saw_injections, "命中路由应注入 routing_injection"
    assert "周报模板" in loop.llm.saw_injections[0]


def test_agent_loop_skips_injection_on_miss():
    m = RoutingMatrix()
    m.add_route(Route(trigger="周报", provider="skill", target="weekly_report"))
    loop = _make_loop(m, lambda r: "### 周报模板\n- 进展")
    loop.run_turn("今天天气如何")
    assert loop.llm.saw_injections == []


def test_agent_loop_gates_routed_tool():
    from vinf_agent.llm import ToolCall

    m = RoutingMatrix()
    m.add_route(Route(trigger="召唤|summon", provider="mcp", target="sl0-mcp", inject=INJECT_TOOL))
    m.bind_server_tools("sl0-mcp", ["summon"])
    registry = ToolRegistry()

    def fake_fn(args):
        return type("R", (), {"ok": True, "output": "executed", "error": "", "terminate": False})()

    registry.register(Tool(name="summon", fn=fake_fn, description="召唤"))

    def resolver(route: Route) -> str:
        return "hint"

    # ---- 未命中触发词 → 工具拒绝 ----
    gate = MemoryGate.__new__(MemoryGate)
    gate.read = lambda: ""
    llm = _FakeLLM().with_tool_calls(
        [ToolCall(id="t1", name="summon", arguments={"strength": 0.5})]
    )
    loop = AgentLoop(llm=llm, tools=registry, gate=gate, router=m, route_resolver=resolver)
    events = []
    loop.run_turn("随便聊聊", events_out=events)
    assert any(e.type == "tool_result" and e.data.get("error") == "routed_inactive" for e in events), \
        "未命中触发词时路由工具应被拒绝"

    # ---- 命中触发词 → 工具放行并执行 ----
    gate = MemoryGate.__new__(MemoryGate)
    gate.read = lambda: ""
    llm = _FakeLLM().with_tool_calls(
        [ToolCall(id="t1", name="summon", arguments={"strength": 0.5})]
    )
    loop = AgentLoop(llm=llm, tools=registry, gate=gate, router=m, route_resolver=resolver)
    events = []
    loop.run_turn("召唤自指循环", events_out=events)
    assert any(e.type == "tool_result" and e.data.get("output") == "executed" for e in events), \
        "命中触发词时路由工具应正常执行"


def test_agent_loop_routes_metadata_in_events():
    m = RoutingMatrix()
    m.add_route(Route(trigger="周报", provider="skill", target="weekly_report"))
    loop = _make_loop(m, lambda r: "内容")
    events = []
    loop.run_turn("写周报", events_out=events)
    assert any(e.type == "route_match" for e in events)