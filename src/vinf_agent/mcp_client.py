"""轻量 MCP 客户端（零依赖，stdio + JSON-RPC 2.0）.

MCP（Model Context Protocol）服务器通过 stdio 与主进程通信。
本模块提供一个最小客户端：initialize → tools/list → tools/call。

- 依赖外部 MCP 服务器（如 npx @modelcontextprotocol/server-filesystem）
- 若环境中无可用 MCP 服务器，相关插件会跳过而不报错
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from typing import Any


class MCPError(RuntimeError):
    pass


class MCPClient:
    """连接单个 stdio MCP 服务器的最小客户端."""

    def __init__(self, name: str, command: str, args: list[str] | None = None):
        self.name = name
        self.command = command
        self.args = args or []
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._next_id = 0
        self._initialized = False

    @property
    def available(self) -> bool:
        """命令是否存在（用于在装配时跳过缺失服务器）."""
        return shutil.which(self.command) is not None

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "vinf-agent", "version": "0.3.0"}})
        self._notify("notifications/initialized", {})
        self._initialized = True

    def _notify(self, method: str, params: dict) -> None:
        """发送 JSON-RPC 通知（无 id，服务器不响应，不能 readline 等待）."""
        if self._proc is None:
            raise MCPError(f"MCP 服务器 {self.name} 未启动")
        with self._lock:
            req = {"jsonrpc": "2.0", "method": method, "params": params}
            line = json.dumps(req, ensure_ascii=False) + "\n"
            assert self._proc.stdin is not None
            self._proc.stdin.write(line)
            self._proc.stdin.flush()

    def _rpc(self, method: str, params: dict) -> Any:
        if self._proc is None:
            raise MCPError(f"MCP 服务器 {self.name} 未启动")
        with self._lock:
            self._next_id += 1
            req = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
            line = json.dumps(req, ensure_ascii=False) + "\n"
            assert self._proc.stdin is not None and self._proc.stdout is not None
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
            resp_line = self._proc.stdout.readline()
            if not resp_line:
                raise MCPError(f"MCP 服务器 {self.name} 无响应")
            resp = json.loads(resp_line)
            if "error" in resp:
                raise MCPError(f"MCP {method} 错误: {resp['error']}")
            return resp.get("result", {})

    def list_tools(self) -> list[dict]:
        """列出服务器可用工具."""
        if not self._initialized:
            self.start()
        result = self._rpc("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> Any:
        """调用服务器工具."""
        if not self._initialized:
            self.start()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        # 提取文本内容拼接返回
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts) if parts else result

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            self._proc = None


def build_mcp_tools(
    servers: list[tuple[str, str, list[str]]],
) -> tuple[dict[str, MCPClient], dict[str, dict]]:
    """根据服务器定义构建工具.

    servers: [(server_name, command, [args])]
    返回 (clients, tool_specs)，tool_specs[name] = {description, parameters}。
    缺失命令的服务器自动跳过。
    """
    clients: dict[str, MCPClient] = {}
    tool_specs: dict[str, dict] = {}
    for name, command, args in servers:
        client = MCPClient(name, command, args)
        if not client.available:
            continue
        clients[name] = client
        try:
            for t in client.list_tools():
                tool_specs[t["name"]] = {
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {}),
                    "_server": name,
                }
        except MCPError:
            # 启动失败则跳过该服务器，不影响整体装配
            clients.pop(name, None)
    return clients, tool_specs