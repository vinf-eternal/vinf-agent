"""MCP 桥接插件：把外部 MCP 服务器工具挂载进 Vinf 工具白名单.

用法：
1. 确保 MCP 服务器可用（如 `npx @modelcontextprotocol/server-filesystem`）
2. 修改下方 MCP_SERVERS 定义
3. 将本文件放入 plugins/ 目录，启动时自动加载

插件协议：模块级 `register(api)` 函数（对齐 pi 的 ExtensionAPI）。
"""
from __future__ import annotations

from vinf_agent.mcp_client import build_mcp_tools
from vinf_agent.tools import ToolResult

# MCP 服务器定义：[(名称, 命令, [参数])]
# 缺失命令的服务器会自动跳过，不影响整体启动。
MCP_SERVERS: list[tuple[str, str, list[str]]] = [
    # 示例：文件系统服务器（需先 npm 全局安装 @modelcontextprotocol/server-filesystem）
    # ("filesystem", "npx", ["-y", "@modelcontextprotocol/server-filesystem", "."]),
]

_clients: dict = {}
_specs: dict[str, dict] = {}


def register(api) -> None:
    global _clients, _specs
    _clients, _specs = build_mcp_tools(MCP_SERVERS)
    if not _specs:
        return

    for tool_name, spec in _specs.items():
        server = spec.get("_server")

        def make_fn(name=tool_name, svr=server):
            def fn(args: dict) -> ToolResult:
                client = _clients.get(svr)
                if client is None:
                    return ToolResult(tool=name, ok=False, error=f"MCP 服务器 {svr} 不可用")
                try:
                    out = client.call_tool(name, args)
                    return ToolResult(tool=name, ok=True, output=out)
                except Exception as e:  # noqa: BLE001
                    return ToolResult(tool=name, ok=False, error=str(e))

            return fn

        api.register_tool(
            name=tool_name,
            fn=make_fn(),
            description=spec.get("description", ""),
            parameters=spec.get("parameters", {}),
        )

    api.register_prompt(
        "通过 MCP 插件桥接了外部工具，需要时可调用以访问外部系统能力。"
    )