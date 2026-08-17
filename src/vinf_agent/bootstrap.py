"""组件装配：CLI 与 Web 共享的构建逻辑."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .agent_loop import AgentLoop
from .config import AgentConfig, ConfigLoader
from .filter import OuterFilter
from .llm import LLMClient, OpenAIClient
from .memory_gate import MemoryGate
from .plugins import load_plugins, render_plugin_prompts
from .providers import resolve_provider
from .skills import load_skills, render_skills_block
from .tools import ToolRegistry, build_tools


class MissingApiKeyError(RuntimeError):
    pass


class MissingConfigError(RuntimeError):
    pass


def load_config(config_dir: Path) -> AgentConfig:
    config = ConfigLoader(config_dir).load()
    if not config.sources:
        raise MissingConfigError(
            f"未找到配置：{config_dir}（可复制 config.example 到 {config_dir}）"
        )
    return config


def build_system_prompt(config: AgentConfig, skill_dir: Path | None = None) -> str:
    """读取 prompts/system.md 并注入 config 摘要与 skills."""
    prompt_file = Path(__file__).resolve().parent.parent.parent / "prompts" / "system.md"
    system_text = (
        prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""
    )
    injection = (
        f"\n<config_injection>\n{config.to_summary() or '(无配置摘要)'}\n</config_injection>\n"
    )
    if skill_dir is not None:
        load = load_skills(skill_dir)
        block = render_skills_block(load.skills)
        if block:
            injection += (
                f"\n<skills_injection>\n"
                f"以下为本会话可用的 Skill 规则（按需遵循，不冲突时叠加）：\n\n"
                f"{block}\n"
                f"</skills_injection>\n"
            )
    return system_text.replace(
        "<config_injection>\n{config_summary}\n</config_injection>", injection
    ).replace("{config_summary}", config.to_summary())


def build_api_key_cmd_resolver(cmd: str) -> Callable[[], str]:
    """构造对齐 pi getApiKey 的 key 解析器：每次请求前执行命令取 key.

    适用于订阅型短期 token（Kimi Code / Copilot 等），命令应输出一行 key。
    """
    import subprocess

    def resolve() -> str:
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            return proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
        except Exception:  # noqa: BLE001
            return ""

    return resolve


def build_agent(
    config_dir: Path,
    api_key: str,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
    memory_dir: Path | None = None,
    outer_filter: OuterFilter | None = None,
    on_event=None,
    skill_dir: Path | None = None,
    plugin_dir: Path | None = None,
    extra_body: dict | None = None,
    max_tokens: int = 2048,
    provider: str | None = None,
    api_key_cmd: str | None = None,
) -> tuple[AgentLoop, AgentConfig, MemoryGate, ToolRegistry]:
    """装配完整 Agent（config → gate → tools → plugins → llm → loop）.

    provider：厂商预置（kimi-coding/claude/github-copilot/openrouter/nvidia 等），
    命中时自动补 base_url；api_key_cmd：每次请求前执行命令动态取 key
    （对齐 pi getApiKey，应对 OAuth 订阅型短期 token）。

    返回 (loop, config, gate, tools)。
    """
    base_url, provider_envs = resolve_provider(provider, base_url)

    if not api_key:
        # provider 指定时，回退到该厂商的 key 环境变量
        import os

        for env in provider_envs:
            if os.environ.get(env):
                api_key = os.environ[env]
                break
    if not api_key and not api_key_cmd:
        # OAuth 订阅登录（kimi-coding 等）无需静态 key：凭据由 resolver 提供
        from .oauth import is_oauth_supported, load_credential

        oauth_ok = provider is not None and is_oauth_supported(provider) and load_credential(provider) is not None
        if not oauth_ok:
            raise MissingApiKeyError(
                "未设置 API key（环境变量 VINF_API_KEY / 厂商专用变量，或 --api-key / --api-key-cmd / --login）"
            )

    config = load_config(config_dir)
    if memory_dir is None:
        memory_dir = Path(config_dir) / "memory"
    gate = MemoryGate(memory_dir)
    tools = build_tools(gate)

    plugin_prompt_parts: list[str] = []
    if plugin_dir is not None:
        plugin_result = load_plugins(plugin_dir, tools)
        plugin_prompt_parts = plugin_result.prompt_parts

    key_resolver = None
    if provider:
        from .oauth import build_oauth_key_resolver, is_oauth_supported, load_credential

        if is_oauth_supported(provider) and load_credential(provider):
            # 订阅型 OAuth：优先用已登录凭据（过期自动 refresh）
            key_resolver = build_oauth_key_resolver(provider)
        elif api_key_cmd:
            # 未登录但给了 --api-key-cmd：手动命令刷新
            key_resolver = build_api_key_cmd_resolver(api_key_cmd)
    elif api_key_cmd:
        key_resolver = build_api_key_cmd_resolver(api_key_cmd)

    llm: LLMClient = OpenAIClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        extra_body=extra_body,
        max_tokens=max_tokens,
        key_resolver=key_resolver,
    )
    system_text = build_system_prompt(config, skill_dir=skill_dir)
    if plugin_prompt_parts:
        system_text += (
            "\n<plugins_injection>\n"
            + "\n\n".join(plugin_prompt_parts)
            + "\n</plugins_injection>\n"
        )
    loop = AgentLoop(
        llm=llm,
        tools=tools,
        gate=gate,
        outer_filter=outer_filter or OuterFilter(),
        system_prompt=system_text,
        on_event=on_event or (lambda e: None),
    )
    return loop, config, gate, tools