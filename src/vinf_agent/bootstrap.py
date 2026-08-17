"""组件装配：CLI 与 Web 共享的构建逻辑."""
from __future__ import annotations

from pathlib import Path

from .agent_loop import AgentLoop
from .config import AgentConfig, ConfigLoader
from .filter import OuterFilter
from .llm import LLMClient, OpenAIClient
from .memory_gate import MemoryGate
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


def build_system_prompt(config: AgentConfig) -> str:
    """读取 prompts/system.md 并注入 config 摘要."""
    prompt_file = Path(__file__).resolve().parent.parent.parent / "prompts" / "system.md"
    system_text = (
        prompt_file.read_text(encoding="utf-8") if prompt_file.is_file() else ""
    )
    injection = (
        f"\n<config_injection>\n{config.to_summary() or '(无配置摘要)'}\n</config_injection>\n"
    )
    return system_text.replace(
        "<config_injection>\n{config_summary}\n</config_injection>", injection
    ).replace("{config_summary}", config.to_summary())


def build_agent(
    config_dir: Path,
    api_key: str,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
    memory_dir: Path | None = None,
    outer_filter: OuterFilter | None = None,
    on_event=None,
) -> tuple[AgentLoop, AgentConfig, MemoryGate, ToolRegistry]:
    """装配完整 Agent（config → gate → tools → llm → loop）.

    返回 (loop, config, gate, tools)。
    """
    config = load_config(config_dir)
    if not api_key:
        raise MissingApiKeyError("未设置 API key（环境变量 VINF_API_KEY 或 --api-key）")

    if memory_dir is None:
        memory_dir = Path(config_dir) / "memory"
    gate = MemoryGate(memory_dir)
    tools = build_tools(gate)

    llm: LLMClient = OpenAIClient(api_key=api_key, base_url=base_url, model=model)
    system_text = build_system_prompt(config)
    loop = AgentLoop(
        llm=llm,
        tools=tools,
        gate=gate,
        outer_filter=outer_filter or OuterFilter(),
        system_prompt=system_text,
        on_event=on_event or (lambda e: None),
    )
    return loop, config, gate, tools