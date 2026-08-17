"""LLM 客户端抽象.

模型 = 外网耗材：本层只定义最小接口 + 一个 OpenAI 兼容的 HTTP 实现。
默认不做任何本地记忆，每次会话上下文由调用方组装。
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str
    stop_reason: str = "end_turn"  # end_turn | length | tool_use | error | aborted
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    def call(self, messages: list[dict]) -> LLMResponse: ...


@dataclass
class OpenAIClient:
    """OpenAI 兼容 chat/completions 客户端（零依赖，urllib 实现）."""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    max_tokens: int = 2048
    temperature: float = 0.7

    def call(self, messages: list[dict]) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return LLMResponse(
                content=f"[LLM 请求失败: HTTP {e.code}]",
                stop_reason="error",
            )
        except Exception as e:  # noqa: BLE001
            return LLMResponse(content=f"[LLM 请求失败: {e}]", stop_reason="error")

        choice = body["choices"][0]
        msg = choice.get("message", {})
        finish = choice.get("finish_reason", "stop")
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                arguments = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=arguments,
                )
            )

        stop_reason = {
            "stop": "end_turn",
            "length": "length",
            "tool_calls": "tool_use",
        }.get(finish, finish)

        return LLMResponse(
            content=msg.get("content", "") or "",
            stop_reason=stop_reason,
            tool_calls=tool_calls,
        )