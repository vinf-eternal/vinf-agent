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
    p.add_argument(
        "--skill-dir",
        default=os.environ.get("VINF_SKILL_DIR", ""),
        help="Skill 目录（默认 <config>/skills；空则禁用 skill 加载）",
    )
    p.add_argument(
        "--plugin-dir",
        default=os.environ.get("VINF_PLUGIN_DIR", ""),
        help="插件目录（默认 <config>/plugins；空则禁用插件加载）",
    )
    p.add_argument(
        "--list-skills",
        action="store_true",
        help="列出 Skill 目录中的可用 skill 并退出",
    )
    p.add_argument(
        "--list-plugins",
        action="store_true",
        help="列出插件目录中的可用插件并退出",
    )
    p.add_argument(
        "--restart-onboard",
        action="store_true",
        help="重触发用户档案采集（覆盖已记录档案）",
    )
    return p


def _resolve_skill_dir(args: argparse.Namespace, config_dir: Path) -> Path | None:
    if args.skill_dir:
        return Path(args.skill_dir)
    default = config_dir / "skills"
    return default if default.is_dir() else None


def _resolve_plugin_dir(args: argparse.Namespace, config_dir: Path) -> Path | None:
    if args.plugin_dir:
        return Path(args.plugin_dir)
    default = config_dir / "plugins"
    return default if default.is_dir() else None


def _list_skills(skill_dir: Path | None) -> int:
    if skill_dir is None:
        print("未找到 skill 目录（可用 --skill-dir 指定）。")
        return 0
    from .skills import load_skills

    load = load_skills(skill_dir)
    print(f"Skill 目录：{skill_dir}")
    for d in load.diagnostics:
        print(f"[warn] {d}")
    if not load.skills:
        print("（无可用 skill）")
        return 0
    for s in load.skills:
        state = "启用" if s.enabled else "禁用"
        print(f"  - {s.name} [{state}] {s.description}")
    return 0


def _list_plugins(plugin_dir: Path | None) -> int:
    if plugin_dir is None:
        print("未找到插件目录（可用 --plugin-dir 指定）。")
        return 0
    from .plugins import load_plugins
    from .tools import ToolRegistry

    registry = ToolRegistry()
    load = load_plugins(plugin_dir, registry)
    print(f"插件目录：{plugin_dir}")
    for f in load.failed:
        print(f"[warn] {f.splitlines()[0]}")
    if not load.loaded:
        print("（无可用插件）")
        return 0
    for name in load.loaded:
        print(f"  + {name}")
    if registry.names():
        print("已注册工具：")
        for n in registry.names():
            print(f"    - {n}")
    return 0


def _maybe_onboard(config_dir: Path) -> None:
    """启动时判定档案进度并引导（agents.md 为唯一进度账本）.

    - NOT_STARTED：完整采集
    - IN_PROGRESS：断点续问缺失项
    - COMPLETE：跳过引导
    """
    from .onboarding import collect_profile, parse_profile, write_profile

    global_md = Path(config_dir) / "global" / "agents.md"
    existing, status = parse_profile(global_md)
    if status == "COMPLETE":
        return

    profile = collect_profile(existing=existing)
    if not profile.answers:
        print("（未填写任何偏好，跳过 onboarding）")
        return
    write_profile(global_md, profile)
    print(f"\n已记录用户档案到 {global_md}，下次启动将自动跳过引导。")


def _force_onboard(config_dir: Path) -> int:
    """--restart-onboard：全量重采并覆盖档案."""
    from .onboarding import collect_profile, write_profile

    global_md = Path(config_dir) / "global" / "agents.md"
    profile = collect_profile(force=True)
    if not profile.answers:
        print("（未填写任何偏好，未覆盖现有档案）")
        return 0
    write_profile(global_md, profile)
    print(f"\n已覆盖用户档案到 {global_md}。")
    return 0


def _run_cli(args: argparse.Namespace, config_dir: Path) -> int:
    _maybe_onboard(config_dir)
    loop, config, _gate, _tools = build_agent(
        config_dir=config_dir,
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        memory_dir=Path(args.memory) if args.memory else None,
        skill_dir=_resolve_skill_dir(args, config_dir),
        plugin_dir=_resolve_plugin_dir(args, config_dir),
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
        skill_dir=_resolve_skill_dir(args, config_dir),
        plugin_dir=_resolve_plugin_dir(args, config_dir),
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

    if args.list_skills:
        return _list_skills(_resolve_skill_dir(args, config_dir))

    if args.list_plugins:
        return _list_plugins(_resolve_plugin_dir(args, config_dir))

    if args.restart_onboard:
        return _force_onboard(config_dir)

    if not args.api_key:
        print("[错误] 未设置 API key（环境变量 VINF_API_KEY 或 --api-key）")
        return 1

    if args.web:
        return _run_web(args, config_dir)
    return _run_cli(args, config_dir)


if __name__ == "__main__":
    raise SystemExit(main())