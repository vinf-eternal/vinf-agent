"""插件加载系统（零依赖，对齐 pi extensions 机制的 Python 版）.

- 插件 = plugins/ 目录下带 `register(api)` 函数的 .py 文件
- api 提供 register_tool / register_prompt 两个钩子
- 插件可注册新的工具（如 MCP 桥接、RSS、文件读取等），扩展工具白名单
- 与 pi 的 ExtensionAPI.registerCommand 同构：第三方扩展能力而不改内核
"""
from __future__ import annotations

import importlib.util
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from .tools import Tool, ToolRegistry


@dataclass
class PluginLoadResult:
    """插件目录加载结果."""

    loaded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    prompt_parts: list[str] = field(default_factory=list)
    plugin_prompts: dict[str, list[str]] = field(default_factory=dict)


class PluginAPI:
    """暴露给插件的扩展钩子（对齐 pi 的 ExtensionAPI）."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self.prompt_parts: list[str] = []

    def register_tool(
        self,
        name: str,
        fn,
        description: str = "",
        parameters: dict | None = None,
    ) -> None:
        """注册一个新工具到白名单（工具 fn: (args: dict) -> ToolResult）."""
        if not callable(fn):
            raise TypeError(f"工具 {name} 的 fn 必须可调用")
        self._registry.register(
            Tool(
                name=name,
                fn=fn,
                description=description,
                parameters=parameters or {},
            )
        )

    def register_prompt(self, text: str) -> None:
        """追加一段系统提示词（用于给模型说明插件提供的工具用法）."""
        if text:
            self.prompt_parts.append(text)


def load_plugins(plugin_dir: Path, registry: ToolRegistry) -> PluginLoadResult:
    """从目录加载所有插件（每个 .py 文件一个插件）."""
    result = PluginLoadResult()
    if not plugin_dir.is_dir():
        return result

    for py in sorted(plugin_dir.glob("*.py")):
        if py.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"vinf_plugin_{py.stem}", py)
            if spec is None or spec.loader is None:
                result.failed.append(f"{py.name}: 无法创建加载器")
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            register = getattr(mod, "register", None)
            if not callable(register):
                result.failed.append(f"{py.name}: 缺少 register(api) 函数")
                continue
            api = PluginAPI(registry)
            register(api)
            result.loaded.append(py.name)
            result.prompt_parts.extend(api.prompt_parts)
            if api.prompt_parts:
                result.plugin_prompts[py.stem] = list(api.prompt_parts)
        except Exception as e:  # noqa: BLE001
            result.failed.append(f"{py.name}: {e}")
            result.failed.append(traceback.format_exc(limit=2))
    return result


def render_plugin_prompts(api_parts: list[str]) -> str:
    """渲染插件追加的系统提示词块."""
    if not api_parts:
        return ""
    return "\n\n".join(api_parts)