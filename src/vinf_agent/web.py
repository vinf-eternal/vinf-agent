"""本地 Web 版：stdlib http.server + 单 HTML 聊天页.

- 自托管，仅监听 localhost，API key 留在本机（数据主权本地）
- GET  /            → 单 HTML 聊天页
- POST /api/chat    → {message} → {response, events, stop_reason}
- GET  /api/status  → {version, model, sources}
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .agent_loop import AgentLoop
from .bootstrap import build_agent
from .llm import LLMResponse

PAGE_FILE = Path(__file__).resolve().parent / "web" / "index.html"

# 单会话状态：本地 Web 版为单用户使用，维持一个会话即可。
_SESSION_LOCK = threading.Lock()
_SESSION_MESSAGES: list[dict] = []


def _page_html() -> str:
    if PAGE_FILE.is_file():
        return PAGE_FILE.read_text(encoding="utf-8")
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Vinf Agent</title></head>"
        "<body><h1>Vinf Agent</h1><p>index.html 缺失</p></body></html>"
    )


class VinfHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, loop: AgentLoop, config_sources: list[str], model: str):
        super().__init__(addr, VinfHandler)
        self.loop = loop
        self.config_sources = config_sources
        self.model = model


class VinfHandler(BaseHTTPRequestHandler):
    server: VinfHTTPServer

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, "text/html; charset=utf-8", _page_html().encode("utf-8"))
        elif path == "/api/status":
            payload = json.dumps(
                {
                    "model": self.server.model,
                    "sources": self.server.config_sources,
                }
            ).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", payload)
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/api/chat":
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            message = str(body.get("message", "")).strip()
        except Exception as e:  # noqa: BLE001
            self._send(400, "application/json; charset=utf-8", json.dumps({"error": str(e)}).encode())
            return
        if not message:
            self._send(400, "application/json; charset=utf-8", json.dumps({"error": "空消息"}).encode())
            return

        events: list[dict] = []
        with _SESSION_LOCK:
            resp: LLMResponse = self.server.loop.run_turn(message, _SESSION_MESSAGES, events_out=events)
        # Event 对象 → 纯 dict（JSON 可序列化）
        events_json = [{"type": e.type, "data": e.data} for e in events]

        payload = json.dumps(
            {
                "response": resp.content,
                "stop_reason": resp.stop_reason,
                "events": events_json,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self._send(200, "application/json; charset=utf-8", payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return  # 静默访问日志，避免刷屏


def serve(
    config_dir: Path,
    api_key: str,
    host: str = "127.0.0.1",
    port: int = 8787,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
    memory_dir: Path | None = None,
) -> VinfHTTPServer:
    """启动本地 Web 版；返回 server，调用方负责 serve_forever."""
    loop, config, _gate, _tools = build_agent(
        config_dir=config_dir,
        api_key=api_key,
        model=model,
        base_url=base_url,
        memory_dir=memory_dir,
    )
    return VinfHTTPServer(
        (host, port), loop=loop, config_sources=config.sources, model=model
    )