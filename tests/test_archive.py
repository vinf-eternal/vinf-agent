"""档案室测试：会话落档 + record_id 回溯 + 回合/摘要结构 + CLI 集成."""
from __future__ import annotations

import json
import time

import pytest

from vinf_agent.archive import (
    SessionArchive,
    TurnRecord,
    find_session,
    list_sessions,
)
from vinf_agent.agent_loop import AgentLoop, Event
from vinf_agent.llm import LLMClient, LLMResponse
from vinf_agent.memory_gate import MemoryGate
from vinf_agent.routing import RoutingMatrix
from vinf_agent.tools import ToolRegistry


def _sample_loop(tmp_path) -> AgentLoop:
    class _LLM(LLMClient):
        def __init__(self):
            pass

        def call(self, messages):
            return LLMResponse(content="收到", stop_reason="end_turn", tool_calls=[])

    return AgentLoop(
        llm=_LLM(),
        tools=ToolRegistry(),
        gate=MemoryGate(tmp_path / "memory"),
    )


# ---------- SessionArchive 基础 ----------


def test_new_session_creates_dir(tmp_path):
    arch = SessionArchive(tmp_path, model="gpt-4o-mini", provider="openai")
    assert arch.dir.is_dir()
    assert arch.dir.name.startswith("sess_")
    meta = json.loads((arch.dir / "session.json").read_text(encoding="utf-8"))
    assert meta["record_id"]
    assert meta["started_iso"]
    assert meta["model"] == "gpt-4o-mini"
    assert meta["provider"] == "openai"
    assert meta["turn_count"] == 0


def test_append_turn_generates_ids(tmp_path):
    arch = SessionArchive(tmp_path)
    arch.append_turn(TurnRecord(turn_id="", ts=1700000000.0, iso="", user_input="你好", response="哈喽"))
    arch.append_turn(TurnRecord(turn_id="", ts=1700000001.0, iso="", user_input="再来", response="好的"))
    turns = arch.read_turns()
    assert len(turns) == 2
    assert turns[0]["turn_id"].endswith("_t1")
    assert turns[1]["turn_id"].endswith("_t2")
    assert turns[0]["ts"] == 1700000000.0
    assert turns[0]["iso"]  # 自动补时间戳
    assert arch.session.turn_count == 2


def test_turn_records_tool_and_routes(tmp_path):
    arch = SessionArchive(tmp_path)
    arch.append_turn(
        TurnRecord(
            turn_id="",
            ts=1700000000.0,
            iso="",
            user_input="召唤自指循环",
            response="已执行",
            stop_reason="end_turn",
            routes_hit=["mcp:sl0-mcp"],
            tool_calls=[{"name": "summon", "ok": True, "output": "ok", "error": ""}],
        )
    )
    turns = arch.read_turns()
    assert turns[0]["routes_hit"] == ["mcp:sl0-mcp"]
    assert turns[0]["tool_calls"][0]["name"] == "summon"


def test_finalize_writes_summary(tmp_path):
    arch = SessionArchive(tmp_path)
    arch.append_turn(
        TurnRecord(
            turn_id="", ts=1700000000.0, iso="", user_input="a", response="b",
            stop_reason="end_turn", routes_hit=["r1"], tool_calls=[
                {"name": "t1", "ok": True, "output": "x", "error": ""},
                {"name": "t1", "ok": False, "output": "", "error": "boom"},
                {"name": "t2", "ok": True, "output": "y", "error": ""},
            ],
        )
    )
    path = arch.finalize()
    assert path.name == "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["turn_count"] == 1
    assert summary["tool_calls"] == {"t1": 2, "t2": 1}
    assert summary["tool_failures"] == 1
    assert summary["routes_hit"] == {"r1": 1}
    assert summary["record_id"] == arch.session.record_id


def test_same_second_avoids_collision(tmp_path):
    arch = SessionArchive(tmp_path)
    arch2 = SessionArchive(tmp_path)
    assert arch.dir != arch2.dir
    assert list_sessions(tmp_path) == [arch.dir, arch2.dir]


def test_append_after_finalize(tmp_path):
    arch = SessionArchive(tmp_path)
    arch.append_turn(TurnRecord(turn_id="", ts=1.0, iso="", user_input="a", response="b"))
    arch.finalize()
    arch.append_turn(TurnRecord(turn_id="", ts=2.0, iso="", user_input="c", response="d"))
    assert arch.session.turn_count == 2
    assert len(arch.read_turns()) == 2


# ---------- list / find ----------


def test_list_and_find(tmp_path):
    arch = SessionArchive(tmp_path)
    arch.append_turn(TurnRecord(turn_id="", ts=1.0, iso="", user_input="a", response="b"))
    arch.finalize()
    assert list_sessions(tmp_path) == [arch.dir]
    assert find_session(tmp_path, arch.dir.name) == arch.dir
    assert find_session(tmp_path, arch.session.record_id) == arch.dir
    assert find_session(tmp_path, "nope") is None


def test_empty_root(tmp_path):
    assert list_sessions(tmp_path / "missing") == []
    assert find_session(tmp_path / "missing", "x") is None


# ---------- CLI 集成：run_session on_turn 落档 ----------


def test_run_session_archive_end_to_end(tmp_path):
    loop = _sample_loop(tmp_path)
    arch = SessionArchive(tmp_path / "archive")

    def on_turn(user_input, response, events):
        tool_calls = []
        routes_hit = []
        for ev in events:
            if ev.type == "tool_result":
                tool_calls.append({"name": ev.data.get("tool", ""), "ok": bool(ev.data.get("ok", True)), "output": "", "error": ""})
            elif ev.type == "route_match":
                routes_hit.extend(ev.data.get("hits", []))
        arch.append_turn(
            TurnRecord(
                turn_id="", ts=time.time(), iso="",
                user_input=user_input, response=response.content,
                stop_reason=response.stop_reason, routes_hit=routes_hit,
                tool_calls=tool_calls,
            )
        )

    inputs = iter(["你好", "再来", None])
    responses = list(loop.run_session(lambda: next(inputs, None), on_turn=on_turn))
    assert len(responses) == 2
    arch.finalize()
    turns = arch.read_turns()
    assert len(turns) == 2
    assert turns[0]["user_input"] == "你好"
    assert turns[0]["response"] == "收到"


def test_run_session_without_on_turn_still_works(tmp_path):
    loop = _sample_loop(tmp_path)
    inputs = iter(["a", None])
    responses = list(loop.run_session(lambda: next(inputs, None)))
    assert len(responses) == 1