"""路由矩阵：agent / MCP / skill / plugin 统一声明式调度（零依赖）.

四类能力提供方（列） → 一行一条路由（行 = 触发信号）：
  - provider=skill   目标为 skill 名，命中注入其 SKILL.md 内容
  - provider=plugin  目标为插件名，命中注入其注册的 prompt_parts
  - provider=mcp     目标为 MCP 服务器名，命中注入该服务器工具提示并放行
  - provider=agent   目标为子 Agent 名，命中注入其人格描述（接口预留）

三个注入位（inject）：
  - system    永久进系统提示词（构建期注入）
  - pre_turn  命中当前消息才注入（运行期临时 system 消息）
  - tool      工具门控：被路由的工具仅在该触发命中时放行，否则拒绝

路由矩阵 = C_ij 耦合矩阵的工程实例化：
  命中判定只做「匹配」（相位 θ），不做时序因果（P21 红线）；
  优先级 = 势垒 B 排序；未命中的能力不进入上下文（P14 自适应势垒）。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# 注入位枚举
INJECT_SYSTEM = "system"
INJECT_PRE_TURN = "pre_turn"
INJECT_TOOL = "tool"

# 提供方枚举
PROVIDER_SKILL = "skill"
PROVIDER_PLUGIN = "plugin"
PROVIDER_MCP = "mcp"
PROVIDER_AGENT = "agent"


@dataclass
class Route:
    """一行路由：触发信号 → 能力提供方 + 注入位."""

    trigger: str          # 触发信号：普通词=子串匹配；re:xxx=正则；tool:xxx=工具名
    provider: str         # skill | plugin | mcp | agent
    target: str           # 目标名（skill/插件/MCP 服务器/子 Agent 名）
    priority: int = 50    # 命中优先级（势垒 B 排序，大者优先）
    inject: str = INJECT_PRE_TURN  # system | pre_turn | tool
    enabled: bool = True
    note: str = ""

    def matches(self, message: str, tool_name: str | None = None) -> bool:
        """触发判定：只做匹配，不做因果."""
        if not self.enabled or not self.trigger:
            return False
        if self.trigger.startswith("re:"):
            try:
                return re.search(self.trigger[3:], message) is not None
            except re.error:
                return False
        if self.trigger.startswith("tool:"):
            pat = self.trigger[5:]
            if tool_name is None:
                return False
            return tool_name == pat or tool_name.startswith(pat.rstrip("*"))
        if self.trigger.startswith("kw:"):
            words = self.trigger[3:].split("|")
            return any(w in message for w in words if w)
        if "|" in self.trigger:
            words = self.trigger.split("|")
            return any(w in message for w in words if w)
        return self.trigger in message


@dataclass
class MCPServer:
    """一个 MCP 能力提供方（stdio server 定义）."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)


class RoutingMatrix:
    """路由矩阵：加载声明式表 + 命中判定 + 注入渲染.

    能力内容解析由外部 resolver 注入（builder 决定如何取 SKILL.md /
    插件 prompt / MCP 工具清单），矩阵本身只做调度。
    """

    def __init__(
        self,
        routes: list[Route] | None = None,
        mcp_servers: list[MCPServer] | None = None,
    ):
        self.routes = routes or []
        self.mcp_servers = mcp_servers or []
        self._server_tools: dict[str, set[str]] = {}

    def bind_server_tools(self, target: str, tool_names: list[str]) -> None:
        """把 MCP 服务器 target 绑定到其具体工具名（工具门控判定用）."""
        if tool_names:
            self._server_tools.setdefault(target, set()).update(tool_names)

    def _concrete(self, target: str) -> set[str]:
        """target → 具体工具名集合；未绑定时把 target 本身当工具名."""
        names = self._server_tools.get(target)
        return set(names) if names else {target}

    # ---- 构建 -----------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> "RoutingMatrix":
        routes = []
        for raw in data.get("routes", []):
            routes.append(
                Route(
                    trigger=raw.get("trigger", ""),
                    provider=raw.get("provider", ""),
                    target=raw.get("target", ""),
                    priority=int(raw.get("priority", 50)),
                    inject=raw.get("inject", INJECT_PRE_TURN),
                    enabled=raw.get("enabled", True),
                    note=raw.get("note", ""),
                )
            )
        servers = []
        for raw in data.get("mcp_servers", []):
            servers.append(
                MCPServer(
                    name=raw.get("name", ""),
                    command=raw.get("command", ""),
                    args=list(raw.get("args", [])),
                )
            )
        return cls(routes=routes, mcp_servers=servers)

    @classmethod
    def load(cls, path: str | Path) -> "RoutingMatrix":
        """从 JSON 文件加载（routes + mcp_servers 两节）."""
        p = Path(path)
        if not p.is_file():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def add_route(self, route: Route) -> None:
        self.routes.append(route)

    # ---- 命中判定 ---------------------------------------------------------

    def match(self, message: str, tool_name: str | None = None) -> list[Route]:
        """对一条消息返回命中的路由，按 priority 降序."""
        hits = [r for r in self.routes if r.matches(message, tool_name)]
        hits.sort(key=lambda r: r.priority, reverse=True)
        return hits

    def system_routes(self) -> list[Route]:
        """永久注入位：构建期全部进系统提示词."""
        return [r for r in self.routes if r.inject == INJECT_SYSTEM and r.enabled]

    def pre_turn_routes(self, message: str) -> list[Route]:
        """本轮注入位：命中当前消息的路由."""
        return self.match(message)

    def routed_tool_names(self) -> set[str]:
        """所有被 tool 注入位路由的目标（展开到具体工具名）."""
        names: set[str] = set()
        for r in self.routes:
            if r.inject == INJECT_TOOL and r.enabled and r.target:
                names |= self._concrete(r.target)
        return names

    def active_tools(self, message: str) -> set[str]:
        """本回合放行的工具集合：命中 tool 路由的 target 展开并集."""
        active: set[str] = set()
        for r in self.match(message):
            if r.inject == INJECT_TOOL and r.target:
                active |= self._concrete(r.target)
        return active

    # ---- 渲染 ---------------------------------------------------------------

    def render(self, hits: list[Route], resolver: Callable[[Route], str]) -> str:
        """把命中路由渲染为注入文本（内容来自 resolver）."""
        parts = []
        for r in hits:
            content = resolver(r)
            if not content:
                continue
            parts.append(
                f"<route trigger=\"{r.trigger}\" provider=\"{r.provider}\" target=\"{r.target}\">\n{content}\n</route>"
            )
        if not parts:
            return ""
        return "\n\n".join(parts)