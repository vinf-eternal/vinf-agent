"""CLI 入口：python -m vinf_agent --config <config_dir> [--web]."""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from .bootstrap import build_agent

BANNER = "Vinf Agent · 个人认知外延系统（开源版）· 输入 exit 结束会话"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vinf_agent", description=BANNER)
    p.add_argument(
        "--env-file",
        default=None,
        help=".env 文件路径（默认自动查找当前/父目录 .env；已存在的环境变量优先）",
    )
    p.add_argument(
        "--config", default="config", help="配置目录（默认 ./config）"
    )
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
    p.add_argument(
        "--max-tokens",
        type=int,
        default=int(os.environ.get("VINF_MAX_TOKENS", "2048")),
        help="单次回复最大 token 数（默认 2048）",
    )
    p.add_argument(
        "--extra-body",
        default=os.environ.get("VINF_EXTRA_BODY", ""),
        help='厂商专属参数 JSON，透传进请求体（如 reasoning 模型: {"chat_template_kwargs":{"enable_thinking":true}}）',
    )
    p.add_argument(
        "--provider",
        default=os.environ.get("VINF_PROVIDER", ""),
        help="厂商预置（kimi-coding/minimax/glm/zai/opencode/qwen-token-plan/github-copilot/openai-codex/deepseek/openai 等），命中自动补 base_url 与 key 环境变量",
    )
    p.add_argument(
        "--api-key-cmd",
        default=os.environ.get("VINF_API_KEY_CMD", ""),
        help="每次请求前执行命令动态取 key（对齐 pi getApiKey，订阅型短期 token 用；命令输出一行 key）",
    )
    p.add_argument(
        "--list-providers",
        action="store_true",
        help="列出厂商预置表并退出",
    )
    p.add_argument(
        "--login",
        metavar="PROVIDER",
        default=None,
        help="订阅型厂商 OAuth 设备码登录（kimi-coding 等），凭据落盘 <credential-dir>/<provider>.json 后退出",
    )
    p.add_argument(
        "--logout",
        metavar="PROVIDER",
        default=None,
        help="删除指定厂商的 OAuth 凭据并退出",
    )
    p.add_argument(
        "--credential-dir",
        default=os.environ.get("VINF_CREDENTIAL_DIR", ""),
        help="OAuth 凭据目录（默认 ~/.vinf/credentials）",
    )
    p.add_argument(
        "--routes",
        default=os.environ.get("VINF_ROUTES", ""),
        help="路由矩阵 JSON 文件（默认 <config>/routes.json；声明 agent/MCP/skill/plugin 四列统一调度）",
    )
    p.add_argument(
        "--mcp-server",
        action="append",
        default=[],
        help="追加 MCP server（格式 name=command,arg1,arg2），可多次指定；与 routes.json 的 mcp_servers 合并",
    )
    p.add_argument(
        "--list-routes",
        action="store_true",
        help="列出路由矩阵配置并退出",
    )
    p.add_argument(
        "--archive-dir",
        default=os.environ.get("VINF_ARCHIVE_DIR", ""),
        help="档案室目录（默认 <config>/archive；每次对话自动落档，带 record_id + 时间戳）",
    )
    p.add_argument(
        "--list-archives",
        action="store_true",
        help="列出全部会话档案（回溯用）并退出",
    )
    return p


def _parse_extra_body(raw: str) -> dict | None:
    if not raw:
        return None
    import json

    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


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


def _resolve_routes_file(args: argparse.Namespace, config_dir: Path) -> Path | None:
    if args.routes:
        return Path(args.routes)
    default = config_dir / "routes.json"
    return default if default.is_file() else None


def _resolve_mcp_servers(args: argparse.Namespace) -> list | None:
    if not args.mcp_server:
        return None
    from .routing import MCPServer

    servers = []
    for spec in args.mcp_server:
        if "=" not in spec:
            continue
        name, rest = spec.split("=", 1)
        parts = rest.split(",")
        servers.append(MCPServer(name=name, command=parts[0], args=parts[1:]))
    return servers or None


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


def _list_routes(routes_file: Path | None) -> int:
    if routes_file is None:
        print("未找到 routes.json（可用 --routes 指定）。")
        return 0
    from .routing import RoutingMatrix

    matrix = RoutingMatrix.load(routes_file)
    print(f"路由矩阵：{routes_file}")
    if not matrix.routes:
        print("（无路由）")
    for r in matrix.routes:
        state = "启用" if r.enabled else "禁用"
        print(f"  [{state}] {r.trigger} → {r.provider}:{r.target} (inject={r.inject}, prio={r.priority})")
    if matrix.mcp_servers:
        print("MCP 提供方：")
        for s in matrix.mcp_servers:
            print(f"  + {s.name}  {s.command} { ' '.join(s.args)}")
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


def _list_providers() -> int:
    from .providers import list_providers

    print("厂商预置表（--provider 命中自动补 base_url 与 key 环境变量）:")
    print(f"{'名称':<20} {'计费':<14} {'base_url':<55} 说明")
    print("-" * 140)
    for p in list_providers():
        billing = "订阅" if p.billing == "subscription" else "按量"
        print(f"{p.name:<20} {billing:<14} {p.base_url:<55} {p.note}")
    print("\n订阅型（kimi-coding/minimax/glm/zai/opencode/qwen-token-plan/github-copilot/")
    print("openai-codex 等）key 多为短期 OAuth token。")
    from .oauth import OAUTH_PROVIDERS

    builtin = ", ".join(OAUTH_PROVIDERS)
    print(f"内置 OAuth 登录（--login）：{builtin}；其余用 --api-key-cmd 每次请求前刷新。")
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


def _credential_dir(args: argparse.Namespace) -> Path | None:
    from .oauth import default_credential_dir

    return Path(args.credential_dir) if args.credential_dir else default_credential_dir()


def _login(args: argparse.Namespace) -> int:
    from .oauth import OAUTH_PROVIDERS, device_login, is_oauth_supported

    if not is_oauth_supported(args.login):
        print(f"[错误] provider {args.login!r} 未内置 OAuth。")
        print(f"已内置: {', '.join(OAUTH_PROVIDERS)}")
        print("其余订阅厂商（minimax/glm/opencode 等）请用 --api-key-cmd 提供 token。")
        return 1
    try:
        token = device_login(args.login, credential_dir=_credential_dir(args))
    except KeyboardInterrupt:
        print("\n已取消。")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[错误] 登录失败: {e}")
        return 1
    print(f"\n登录成功，凭据已保存（有效期至 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token.expires_at))}）")
    print("下次启动使用同一 provider 即可自动使用订阅 token，过期自动刷新。")
    return 0


def _logout(args: argparse.Namespace) -> int:
    from .oauth import clear_credential

    if clear_credential(args.logout, _credential_dir(args)):
        print(f"已删除 {args.logout} 的 OAuth 凭据。")
    else:
        print(f"未找到 {args.logout} 的 OAuth 凭据。")
    return 0


def _resolve_archive_dir(args: argparse.Namespace, config_dir: Path) -> Path:
    if args.archive_dir:
        return Path(args.archive_dir)
    return config_dir / "archive"


def _list_archives(archive_dir: Path) -> int:
    from .archive import list_sessions

    sessions = list_sessions(archive_dir)
    print(f"档案室：{archive_dir}")
    if not sessions:
        print("（暂无会话档案）")
        return 0
    for d in sessions:
        meta_file = d / "session.json"
        summary_file = d / "summary.json"
        if not meta_file.is_file():
            print(f"  {d.name}  （无元数据）")
            continue
        import json as _json

        meta = _json.loads(meta_file.read_text(encoding="utf-8"))
        summary = {}
        if summary_file.is_file():
            summary = _json.loads(summary_file.read_text(encoding="utf-8"))
        print(
            f"  {meta['session_id']:<24} {meta['started_iso']}  "
            f"回合={meta['turn_count']:<3} 模型={meta.get('model','')}  "
            f"record_id={meta['record_id']}"
        )
        if summary.get("routes_hit"):
            print(f"     路由命中: {summary['routes_hit']}")
        if summary.get("tool_calls"):
            print(f"     工具调用: {summary['tool_calls']}")
    print(f"\n共 {len(sessions)} 个会话档案。可用 record_id 回溯（archive/sess_*/turns.jsonl）。")
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
        extra_body=_parse_extra_body(args.extra_body),
        max_tokens=args.max_tokens,
        provider=args.provider or None,
        api_key_cmd=args.api_key_cmd or None,
        routes_file=_resolve_routes_file(args, config_dir),
        mcp_servers=_resolve_mcp_servers(args),
    )
    print(BANNER)
    print(f"配置来源: {', '.join(config.sources)}")

    from .archive import SessionArchive, TurnRecord

    archive = SessionArchive(
        _resolve_archive_dir(args, config_dir),
        model=args.model,
        provider=args.provider or "",
    )
    print(f"档案室: 本会话 record_id={archive.session.record_id} → {archive.dir}")

    def input_provider():
        try:
            return input("你 > ").strip() or None
        except (EOFError, KeyboardInterrupt):
            return None

    def on_turn(user_input: str, response, events: list) -> None:
        tool_calls: list[dict] = []
        routes_hit: list[str] = []
        for ev in events:
            if ev.type == "tool_call_start":
                for nm in ev.data.get("names", []):
                    tool_calls.append(
                        {"name": nm, "ok": None, "output": "", "error": ""}
                    )
            elif ev.type == "tool_result":
                nm = ev.data.get("tool", "")
                entry = next((t for t in tool_calls if t["name"] == nm), None)
                if entry is not None:
                    entry["ok"] = bool(ev.data.get("ok", True))
                    entry["output"] = str(ev.data.get("output", "") or "")[:500]
                    entry["error"] = ev.data.get("error", "")
            elif ev.type == "route_match":
                routes_hit.extend(ev.data.get("hits", []))
        archive.append_turn(
            TurnRecord(
                turn_id="",
                ts=time.time(),
                iso="",
                user_input=user_input,
                response=response.content,
                stop_reason=response.stop_reason,
                model=args.model,
                routes_hit=routes_hit,
                tool_calls=tool_calls,
            )
        )

    for response in loop.run_session(input_provider, on_turn=on_turn):
        print(f"Vinf > {response.content}")
        if response.stop_reason in ("error", "aborted"):
            break
        if response.content.strip().lower() in ("exit", "退出"):
            break

    summary_path = archive.finalize()
    print(f"会话结束。档案已落盘：{summary_path}")
    print(f"record_id={archive.session.record_id} 回合={archive.session.turn_count} 回溯用 --list-archives")
    print("记忆已持久化于本地。")
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
        extra_body=_parse_extra_body(args.extra_body),
        max_tokens=args.max_tokens,
        provider=args.provider or None,
        api_key_cmd=args.api_key_cmd or None,
        routes_file=_resolve_routes_file(args, config_dir),
        mcp_servers=_resolve_mcp_servers(args),
    )
    print(f"Vinf Agent Web 版已启动：http://{args.host}:{args.port}")
    print("记忆留在本机（PrivateCore），模型仅做外网耗材。Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


def _preload_env(argv: list[str] | None) -> None:
    """在 build_parser 之前加载 .env（argparse 默认值依赖 os.environ）.

    手动预扫描 argv 里的 --env-file，避免先建 parser 再加载导致默认值取空。
    """
    from .env import load_dotenv

    explicit = None
    if argv:
        for i, token in enumerate(argv):
            if token == "--env-file" and i + 1 < len(argv):
                explicit = argv[i + 1]
                break
            if token.startswith("--env-file="):
                explicit = token.split("=", 1)[1]
                break
    loaded = load_dotenv(explicit=explicit)
    if loaded is not None:
        print(f"[env] 已加载 {loaded}")


def main(argv: list[str] | None = None) -> int:
    _preload_env(argv)
    args = build_parser().parse_args(argv)
    config_dir = Path(args.config)

    if args.list_skills:
        return _list_skills(_resolve_skill_dir(args, config_dir))

    if args.list_plugins:
        return _list_plugins(_resolve_plugin_dir(args, config_dir))

    if args.list_routes:
        return _list_routes(_resolve_routes_file(args, config_dir))

    if args.list_archives:
        return _list_archives(_resolve_archive_dir(args, config_dir))

    if args.list_providers:
        return _list_providers()

    if args.login:
        return _login(args)

    if args.logout:
        return _logout(args)

    if args.restart_onboard:
        return _force_onboard(config_dir)

    if not args.api_key and not args.provider and not args.api_key_cmd:
        print("[错误] 未设置 API key（环境变量 VINF_API_KEY / 厂商专用变量，或 --api-key / --provider / --api-key-cmd）")
        return 1

    if args.web:
        return _run_web(args, config_dir)
    return _run_cli(args, config_dir)


if __name__ == "__main__":
    raise SystemExit(main())