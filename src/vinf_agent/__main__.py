"""CLI 入口：python -m vinf_agent --config <config_dir> [--web]."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .bootstrap import build_agent

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
    p.add_argument(
        "--web",
        action="store_true",
        help="启动本地 Web 版（自托管，仅监听 localhost）",
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("VINF_PORT", "8787")),
        help="Web 端口（默认 8787）",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("VINF_HOST", "127.0.0.1"),
        help="Web 监听地址（默认 127.0.0.1，勿改 0.0.0.0）",
    )
    return p


def _run_cli(args: argparse.Namespace, config_dir: Path) -> int:
    loop, config, _gate, _tools = build_agent(
        config_dir=config_dir,
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        memory_dir=Path(args.memory) if args.memory else None,
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


def _run_web(args: argparse.Namespace, config_dir: Path) -> int:
    from .web import serve

    server = serve(
        config_dir=config_dir,
        api_key=args.api_key,
        host=args.host,
        port=args.port,
        model=args.model,
        base_url=args.base_url,
        memory_dir=Path(args.memory) if args.memory else None,
    )
    print(f"Vinf Agent Web 版已启动：http://{args.host}:{args.port}")
    print("记忆留在本机（PrivateCore），模型仅做外网耗材。Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_dir = Path(args.config)

    if not args.api_key:
        print("[错误] 未设置 API key（环境变量 VINF_API_KEY 或 --api-key）")
        return 1

    if args.web:
        return _run_web(args, config_dir)
    return _run_cli(args, config_dir)


if __name__ == "__main__":
    raise SystemExit(main())