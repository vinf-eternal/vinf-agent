"""CLI 入口：python -m vinf_agent --config <config_dir>."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .agent_loop import AgentLoop
from .config import ConfigLoader
from .filter import OuterFilter
from .llm import OpenAIClient
from .memory_gate import MemoryGate
from .tools import build_tools

BANNER = "Vinf Agent · 个人认知外延系统（开源版）· 输入 exit 结束会话"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vinf_agent", description=BANNER)
    p.add_argument("--config", default="config", help="配置目录（默认 ./config）")
    p.add_argument("--memory", default=None, help="记忆目录（默认 <config>/memory）")
    p.add_argument(
        "--model",
        default=os.environ.get("VINF_MODEL", "gpt-4o-mini"),
        help="模型名（模型=外网耗材，可任意更换）",
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("VINF_BASE_URL", "https://api.openai.com/v1"),
        help="OpenAI 兼容 API 地址",
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("VINF_API_KEY", ""),
        help="API key（缺省读环境变量 VINF_API_KEY）",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_dir = Path(args.config)

    loader = ConfigLoader(config_dir)
    config = loader.load()
    if not config.sources:
        print(f"[错误] 未找到配置：{config_dir}（可复制 config.example 到 {config_dir}）")
        return 1

    memory_dir = Path(args.memory) if args.memory else config_dir / "memory"
    gate = MemoryGate(memory_dir)
    tools = build_tools(gate)

    if not args.api_key:
        print("[错误] 未设置 API key（环境变量 VINF_API_KEY 或 --api-key）")
        return 1

    llm = OpenAIClient(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
    )

    system_prompt = Path(__file__).resolve().parent.parent.parent / "prompts" / "system.md"
    system_text = system_prompt.read_text(encoding="utf-8") if system_prompt.is_file() else ""
    injection = f"\n<config_injection>\n{config.to_summary() or '(无配置摘要)'}\n</config_injection>\n"
    system_text = system_text.replace(
        "{config_summary}", config.to_summary()
    ).replace(
        "<config_injection>\n{config_summary}\n</config_injection>", injection
    )

    loop = AgentLoop(
        llm=llm,
        tools=tools,
        gate=gate,
        outer_filter=OuterFilter(),
        system_prompt=system_text,
        on_event=lambda e: None,
    )

    print(BANNER)
    print(f"配置来源: {', '.join(config.sources)}")

    def input_provider():
        try:
            return input("你 > ").strip() or None
        except (EOFError, KeyboardInterrupt):
            return None

    for response in loop.run_session(input_provider):
        print(f"Vinf > {response.content}")
        if response.stop_reason in ("error", "aborted"):
            break
        if response.content.strip().lower() in ("exit", "退出"):
            break

    print("会话结束。记忆已持久化于本地。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())