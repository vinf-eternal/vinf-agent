"""双层循环 Agent 内核（外环交互 + 内环工具）.

对齐 pi `packages/agent/src/agent-loop.ts` 的 runLoop 语义：
- 外环 while(True)：collect steering → 注入 → llm_call → 检查 stop_reason → 产出回复
- 内环 while(hasMoreToolCalls)：提取工具调用 → length-stop 防残缺 → 执行 → 回填 → 再生成

事件流（对齐 pi EventStream）：agent_start/turn_start/message_start/message_end/
tool_call_start/tool_result/turn_end/agent_end
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator

from .filter import OuterFilter
from .llm import LLMClient, LLMResponse, ToolCall
from .memory_gate import MemoryGate
from .tools import ToolRegistry


@dataclass
class Event:
    type: str
    data: dict = field(default_factory=dict)


class AgentLoop:
    """双层循环执行体."""

    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        gate: MemoryGate,
        outer_filter: OuterFilter | None = None,
        system_prompt: str = "",
        on_event: Callable[[Event], None] | None = None,
        max_inner_iterations: int = 20,
    ):
        self.llm = llm
        self.tools = tools
        self.gate = gate
        self.outer_filter = outer_filter or OuterFilter()
        self.system_prompt = system_prompt
        self.on_event = on_event or (lambda e: None)
        self.max_inner_iterations = max_inner_iterations
        self._events_out: list[Event] | None = None

    def _emit(self, etype: str, **data) -> None:
        event = Event(type=etype, data=data)
        self.on_event(event)
        if self._events_out is not None:
            self._events_out.append(event)

    def _context(self, messages: list[dict]) -> list[dict]:
        return [{"role": "system", "content": self.system_prompt}, *messages]

    def _call(self, messages: list[dict]) -> LLMResponse:
        self._emit("message_start")
        resp = self.llm.call(self._context(messages))
        self._emit("message_end", content=resp.content, stop_reason=resp.stop_reason)
        return resp

    def _extract_tool_calls(self, resp: LLMResponse) -> list[ToolCall]:
        return resp.tool_calls

    def _fail_all(self, calls: list[ToolCall]) -> list[dict]:
        """length 截断 → 全部失败，防残缺参数执行（pi failToolCallsFromTruncatedMessage）."""
        self._emit("tool_call_start", names=[c.name for c in calls], truncated=True)
        results = []
        for c in calls:
            result = {
                "role": "tool",
                "tool_call_id": c.id,
                "content": f"[截断] 工具 {c.name} 参数不完整，未执行",
            }
            results.append(result)
            self._emit("tool_result", tool=c.name, ok=False, error="truncated_args")
        return results

    def _execute(self, calls: list[ToolCall]) -> tuple[list[dict], bool]:
        """执行工具，返回 (回填结果, terminate)."""
        self._emit("tool_call_start", names=[c.name for c in calls])
        backfills: list[dict] = []
        terminate = False
        for c in calls:
            tool = self.tools.get(c.name)
            if tool is None:
                backfills.append(
                    {
                        "role": "tool",
                        "tool_call_id": c.id,
                        "content": f"[未知工具] {c.name}",
                    }
                )
                self._emit("tool_result", tool=c.name, ok=False, error="unknown_tool")
                continue
            r = tool.fn(c.arguments)
            backfills.append(
                {
                    "role": "tool",
                    "tool_call_id": c.id,
                    "content": str(r.output) if r.ok else f"[错误] {r.error}",
                }
            )
            self._emit(
                "tool_result",
                tool=c.name,
                ok=r.ok,
                output=r.output,
                error=r.error,
            )
            if r.terminate:
                terminate = True
        return backfills, terminate

    def run_turn(self, user_input: str, messages: list[dict] | None = None, events_out: list[Event] | None = None) -> LLMResponse:
        """一次外环迭代：处理一条用户输入，产出完整回复（含内环）."""
        self._events_out = events_out
        try:
            return self._run_turn_impl(user_input, messages)
        finally:
            self._events_out = None

    def _run_turn_impl(self, user_input: str, messages: list[dict] | None) -> LLMResponse:
        messages = messages or []
        cleaned = self.outer_filter.filter(user_input)
        self._emit("turn_start", input_len=len(cleaned))
        messages.append({"role": "user", "content": cleaned})

        response = self._call(messages)
        if response.stop_reason in ("error", "aborted"):
            self._emit("turn_end", stop_reason=response.stop_reason)
            return response

        has_more_tools = bool(self._extract_tool_calls(response))
        iterations = 0
        terminate = False
        while has_more_tools and not terminate and iterations < self.max_inner_iterations:
            iterations += 1
            calls = self._extract_tool_calls(response)
            if not calls:
                has_more_tools = False
                continue
            if response.stop_reason == "length":
                backfills = self._fail_all(calls)
            else:
                backfills, terminate = self._execute(calls)
            messages.extend(backfills)
            response = self._call(messages)
            has_more_tools = bool(self._extract_tool_calls(response))

        self._emit("turn_end", stop_reason=response.stop_reason)
        return response

    def run_session(self, input_provider: Callable[[], str | None]) -> Iterator[LLMResponse]:
        """外环：持续收集用户输入（steering 可打断），产出完整回复.

        input_provider 每次被调用返回一条用户输入；返回 None 表示会话结束。
        yield 每条用户输入对应的完整回复（含内环工具执行后的最终生成）。
        """
        self._emit("agent_start")
        messages: list[dict] = []
        # 会话起始注入私人记忆（B_in 读取，只读）
        memory = self.gate.read()
        if memory:
            messages.append({"role": "system", "content": f"[私人记忆]\n{memory}"})

        while True:
            user_input = input_provider()
            if user_input is None:
                break
            response = self.run_turn(user_input, messages)
            yield response
            if response.stop_reason in ("error", "aborted"):
                break
        self._emit("agent_end")