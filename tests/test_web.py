"""本地 Web 版测试：真实 HTTP 回环 + 工具事件透传."""
import json
import threading
import urllib.request
from pathlib import Path

from vinf_agent import __version__
from vinf_agent.llm import LLMResponse, ToolCall
from vinf_agent.web import VinfHTTPServer
from vinf_agent.agent_loop import AgentLoop
from vinf_agent.filter import OuterFilter
from vinf_agent.memory_gate import MemoryGate
from vinf_agent.tools import build_tools


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def call(self, messages):
        return self.responses.pop(0)


def _start(tmp_path, responses):
    gate = MemoryGate(tmp_path / "memory")
    tools = build_tools(gate)
    loop = AgentLoop(
        llm=FakeLLM(responses),
        tools=tools,
        gate=gate,
        outer_filter=OuterFilter(),
        system_prompt="测试系统提示词",
    )
    server = VinfHTTPServer(("127.0.0.1", 0), loop, ["global/agents.md"], "test-model")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    return server, base


def _post(base, path, payload):
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_index_page(tmp_path):
    server, base = _start(tmp_path, [])
    try:
        with urllib.request.urlopen(f"{base}/") as resp:
            html = resp.read().decode("utf-8")
        assert "Vinf Agent" in html
    finally:
        server.shutdown()


def test_status_endpoint(tmp_path):
    server, base = _start(tmp_path, [])
    try:
        with urllib.request.urlopen(f"{base}/api/status") as resp:
            j = json.loads(resp.read().decode("utf-8"))
        assert j["model"] == "test-model"
        assert j["sources"] == ["global/agents.md"]
    finally:
        server.shutdown()


def test_chat_simple(tmp_path):
    server, base = _start(tmp_path, [LLMResponse(content="你好，世界")])
    try:
        j = _post(base, "/api/chat", {"message": "hi"})
        assert j["response"] == "你好，世界"
        assert j["stop_reason"] == "end_turn"
    finally:
        server.shutdown()


def test_chat_tool_events(tmp_path):
    server, base = _start(
        tmp_path,
        [
            LLMResponse(
                content="",
                stop_reason="tool_use",
                tool_calls=[ToolCall(id="c1", name="exit_session", arguments={})],
            ),
            LLMResponse(content="已退出"),
        ],
    )
    try:
        j = _post(base, "/api/chat", {"message": "退出"})
        assert j["response"] == "已退出"
        types = [e["type"] for e in j["events"]]
        assert "tool_call_start" in types
        assert "tool_result" in types
    finally:
        server.shutdown()


def test_chat_empty_message(tmp_path):
    server, base = _start(tmp_path, [])
    try:
        import urllib.error

        try:
            _post(base, "/api/chat", {"message": "   "})
            assert False, "应当返回 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            j = json.loads(e.read().decode("utf-8"))
            assert j["error"]
    finally:
        server.shutdown()


def test_chat_sequence_state(tmp_path):
    """同一会话多轮：messages 状态在服务端持续累积."""
    server, base = _start(tmp_path, [LLMResponse(content="答1"), LLMResponse(content="答2")])
    try:
        r1 = _post(base, "/api/chat", {"message": "q1"})
        r2 = _post(base, "/api/chat", {"message": "q2"})
        assert r1["response"] == "答1"
        assert r2["response"] == "答2"
    finally:
        server.shutdown()