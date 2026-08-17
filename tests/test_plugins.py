"""plugins.py 加载系统测试."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from vinf_agent.plugins import (  # noqa: E402
    PluginAPI,
    load_plugins,
    render_plugin_prompts,
)
from vinf_agent.tools import ToolRegistry, ToolResult  # noqa: E402


def test_plugin_registers_tool(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "echo.py").write_text(
        "from vinf_agent.tools import ToolResult\n"
        "def register(api):\n"
        "    def fn(args):\n"
        "        return ToolResult(tool='echo', ok=True, output=args.get('text',''))\n"
        "    api.register_tool('echo', fn, description='回显')\n",
        encoding="utf-8",
    )
    registry = ToolRegistry()
    result = load_plugins(plugin_dir, registry)
    assert result.loaded == ["echo.py"]
    assert "echo" in registry.names()
    tool = registry.get("echo")
    assert tool is not None
    out = tool.fn({"text": "hello"})
    assert out.ok and out.output == "hello"


def test_plugin_without_register_reports_failed(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "bad.py").write_text("x = 1\n", encoding="utf-8")
    registry = ToolRegistry()
    result = load_plugins(plugin_dir, registry)
    assert result.loaded == []
    assert len(result.failed) == 1


def test_plugin_register_prompt(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "prompter.py").write_text(
        "def register(api):\n"
        "    api.register_prompt('插件提示词测试')\n",
        encoding="utf-8",
    )
    registry = ToolRegistry()
    result = load_plugins(plugin_dir, registry)
    assert "插件提示词测试" in result.prompt_parts


def test_plugin_skips_underscore_files(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "_internal.py").write_text("raise Exception('不应加载')\n", encoding="utf-8")
    registry = ToolRegistry()
    result = load_plugins(plugin_dir, registry)
    assert result.loaded == []
    assert result.failed == []


def test_render_plugin_prompts():
    text = render_plugin_prompts(["a", "b"])
    assert text == "a\n\nb"
    assert render_plugin_prompts([]) == ""


def test_pluginapi_register_tool_validates_callable():
    api = PluginAPI(ToolRegistry())
    try:
        api.register_tool("bad", "not-callable")
        assert False, "应拒绝非可调用 fn"
    except TypeError:
        pass