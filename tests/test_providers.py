"""providers 注册表 + api-key-cmd 动态 key 解析测试."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vinf_agent.bootstrap import build_api_key_cmd_resolver, build_agent
from vinf_agent.providers import (
    PROVIDERS,
    is_subscription,
    list_providers,
    resolve_provider,
)


def test_provider_list_nonempty():
    assert len(PROVIDERS) >= 10


def test_deepseek_is_paygo():
    assert is_subscription("deepseek") is False


def test_subscription_providers_flagged():
    for name in ("kimi-coding", "minimax", "glm", "zai", "opencode",
                 "qwen-token-plan", "github-copilot", "openai-codex"):
        assert is_subscription(name) is True, name


def test_resolve_provider_missing_uses_default():
    url, envs = resolve_provider(None, None)
    assert url.startswith("https://")
    assert "VINF_API_KEY" in envs


def test_resolve_provider_override_base_url():
    url, _envs = resolve_provider("openai", "https://proxy.example/v1")
    assert url == "https://proxy.example/v1"


def test_resolve_kimi_coding_base_url():
    url, envs = resolve_provider("kimi-coding", None)
    assert url == "https://api.kimi.com/coding"
    assert "KIMI_API_KEY" in envs


def test_resolve_glm_base_url():
    url, _envs = resolve_provider("glm", None)
    assert "bigmodel.cn" in url


def test_list_providers_has_specs():
    specs = list_providers()
    assert any(s.name == "deepseek" and s.billing == "paygo" for s in specs)
    assert any(s.name == "kimi-coding" and s.billing == "subscription" for s in specs)


def test_build_api_key_cmd_resolver_success():
    code = "from sys import stdout; stdout.write('tok_123')"
    resolver = build_api_key_cmd_resolver(f"{sys.executable} -c {code!r}")
    assert resolver() == "tok_123"


def test_build_api_key_cmd_resolver_empty_output():
    resolver = build_api_key_cmd_resolver(f"{sys.executable} -c \"\"")
    assert resolver() == ""


def test_build_api_key_cmd_resolver_multiline_takes_first():
    resolver = build_api_key_cmd_resolver(
        f"{sys.executable} -c \"print('a'); print('b')\""
    )
    assert resolver() == "a"


def test_build_api_key_cmd_resolver_failure_returns_empty():
    resolver = build_api_key_cmd_resolver("definitely-not-a-command-xyz")
    assert resolver() == ""


def test_llm_uses_key_resolver_over_static(monkeypatch):
    """key_resolver 优先级高于 api_key（对齐 pi getApiKey）."""
    from vinf_agent.llm import OpenAIClient

    captured = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"id":"x","choices":[{"message":{"content":"hi"}}]}'

    def fake_urlopen(req, **kwargs):
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = req.data
        return FakeResp()

    monkeypatch.setattr("vinf_agent.llm.urllib.request.urlopen", fake_urlopen)
    client = OpenAIClient(
        api_key="static_key",
        base_url="https://example.com/v1",
        model="m",
        key_resolver=lambda: "dynamic_key",
    )
    resp = client.call([{"role": "user", "content": "x"}])
    assert resp.content == "hi"
    assert captured["auth"] == "Bearer dynamic_key"


def test_build_agent_with_api_key_cmd_only(tmp_path, monkeypatch):
    """仅有 --api-key-cmd（无静态 key）时也能装配（key 为空由 resolver 补）."""
    monkeypatch.setenv("VINF_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "global").mkdir()
    (config_dir / "memory").mkdir()
    (config_dir / "global" / "agents.md").write_text("# global\n", encoding="utf-8")

    loop, config, gate, tools = build_agent(
        config_dir=config_dir,
        api_key="",
        provider="deepseek",
        api_key_cmd="echo dynamic-token",
    )
    assert loop is not None
    assert gate is not None
    assert tools is not None