"""工具注册与执行（内环工具循环的算子库）.

- 工具调用返回 result + terminate 标志（某工具可强制终止内环）
- 所有工具由白名单注册，无任意代码执行能力（开源版裁剪）
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from .memory_gate import MemoryGate


@dataclass
class ToolResult:
    tool: str
    ok: bool
    output: Any = None
    error: str = ""
    terminate: bool = False


ToolFn = Callable[[dict], ToolResult]


@dataclass
class Tool:
    name: str
    fn: ToolFn
    description: str = ""
    parameters: dict = field(default_factory=dict)


class ToolRegistry:
    """工具白名单注册表."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]


def _memory_write(gate: MemoryGate):
    def fn(args: dict) -> ToolResult:
        title = args.get("title", "note")
        text = args.get("text", "")
        try:
            gate.write(title, text)
        except ValueError as e:
            return ToolResult(tool="memory_write", ok=False, error=str(e))
        return ToolResult(tool="memory_write", ok=True, output=f"已保存到 memory/{title}.md")

    return fn


def _memory_read(gate: MemoryGate):
    def fn(args: dict) -> ToolResult:
        return ToolResult(tool="memory_read", ok=True, output=gate.read())

    return fn


def _exit_session(args: dict) -> ToolResult:
    return ToolResult(tool="exit_session", ok=True, output="会话结束", terminate=True)


def build_tools(gate: MemoryGate) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        Tool(
            name="memory_write",
            fn=_memory_write(gate),
            description="写入一条私人记忆（需通过价值判断）",
            parameters={"title": {"type": "string"}, "text": {"type": "string"}},
        )
    )
    reg.register(
        Tool(
            name="memory_read",
            fn=_memory_read(gate),
            description="读取全部私人记忆",
            parameters={},
        )
    )
    reg.register(
        Tool(
            name="exit_session",
            fn=_exit_session,
            description="结束当前会话（终止内环）",
            parameters={},
        )
    )
    return reg