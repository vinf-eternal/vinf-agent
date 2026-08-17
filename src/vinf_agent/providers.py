"""厂商预置表：订阅型 Coding API 即插即用（对齐 pi providers 体系）.

每个 provider 定义 base_url + key 环境变量候选列表。订阅型服务（Kimi Code /
MiniMax / GLM(Z.AI) / OpenCode / Qwen Token Plan / Copilot 等）的 key 多为短期
OAuth token，建议配合 --api-key-cmd 每次请求前动态刷新（对齐 pi getApiKey）。

注：openai-codex 走 chatgpt.com/backend-api OAuth，无公开 API key env，必须
用 --api-key-cmd 提供 token。
"""
from __future__ import annotations

from dataclasses import dataclass

# provider 名 → (base_url, [key 环境变量候选], 计费模式, 说明)
# 计费模式: "subscription" 订阅制（短期 token，建议动态刷新）| "paygo" 按量计费（静态 key）
PROVIDERS: dict[str, tuple[str, list[str], str, str]] = {
    "deepseek": (
        "https://api.deepseek.com/v1",
        ["DEEPSEEK_API_KEY", "VINF_API_KEY"],
        "paygo",
        "DeepSeek 官方（传统按量计费，静态 key）",
    ),
    "openai": (
        "https://api.openai.com/v1",
        ["OPENAI_API_KEY", "VINF_API_KEY"],
        "paygo",
        "OpenAI",
    ),
    "nvidia": (
        "https://integrate.api.nvidia.com/v1",
        ["NVIDIA_API_KEY", "VINF_API_KEY"],
        "paygo",
        "NVIDIA NIM（按量）",
    ),
    "kimi-coding": (
        "https://api.kimi.com/coding",
        ["KIMI_API_KEY", "MOONSHOT_API_KEY", "VINF_API_KEY"],
        "subscription",
        "Kimi Code 订阅（OAuth 短期 token）",
    ),
    "minimax": (
        "https://api.minimax.io/anthropic",
        ["MINIMAX_API_KEY", "VINF_API_KEY"],
        "subscription",
        "MiniMax 订阅",
    ),
    "minimax-cn": (
        "https://api.minimaxi.com/anthropic",
        ["MINIMAX_CN_API_KEY", "VINF_API_KEY"],
        "subscription",
        "MiniMax 国内订阅",
    ),
    "glm": (
        "https://open.bigmodel.cn/api/coding/paas/v4",
        ["ZAI_CODING_CN_API_KEY", "GLM_API_KEY", "VINF_API_KEY"],
        "subscription",
        "智谱 GLM Coding（Z.AI Coding CN，订阅）",
    ),
    "zai": (
        "https://api.z.ai/api/coding/paas/v4",
        ["ZAI_API_KEY", "VINF_API_KEY"],
        "subscription",
        "Z.AI Coding（海外，订阅）",
    ),
    "opencode": (
        "https://api.opencode.ai/v1",
        ["OPENCODE_API_KEY", "VINF_API_KEY"],
        "subscription",
        "OpenCode 订阅",
    ),
    "qwen-token-plan": (
        "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        ["QWEN_TOKEN_PLAN_API_KEY", "VINF_API_KEY"],
        "subscription",
        "通义 Qwen Token Plan（订阅）",
    ),
    "github-copilot": (
        "https://api.individual.githubcopilot.com",
        ["COPILOT_GITHUB_TOKEN", "COPILOT_API_KEY", "VINF_API_KEY"],
        "subscription",
        "GitHub Copilot 个人订阅（OAuth token）",
    ),
    "openai-codex": (
        "https://chatgpt.com/backend-api",
        ["OPENAI_CODEX_TOKEN", "VINF_API_KEY"],
        "subscription",
        "OpenAI Codex（ChatGPT 订阅，仅 OAuth token，必须 --api-key-cmd）",
    ),
    "openrouter": (
        "https://openrouter.ai/api/v1",
        ["OPENROUTER_API_KEY", "VINF_API_KEY"],
        "paygo",
        "OpenRouter 聚合（按量）",
    ),
    "claude": (
        "https://api.anthropic.com/v1",
        ["ANTHROPIC_API_KEY", "VINF_API_KEY"],
        "paygo",
        "Anthropic Claude（原生协议需转 OpenAI 兼容网关）",
    ),
}


@dataclass
class ProviderSpec:
    name: str
    base_url: str
    env_vars: list[str]
    billing: str
    note: str = ""


def resolve_provider(name: str | None, base_url: str | None) -> tuple[str, list[str]]:
    """解析 provider 名 → (base_url, [key env 候选]).

    未指定 provider 或未命中时，返回传入的 base_url（或 openai 默认）与通用 env。
    """
    if name and name in PROVIDERS:
        url, envs, _billing, _note = PROVIDERS[name]
        return (base_url or url), envs
    return (base_url or PROVIDERS["openai"][0]), ["VINF_API_KEY", "OPENAI_API_KEY"]


def is_subscription(provider: str | None) -> bool:
    if provider and provider in PROVIDERS:
        return PROVIDERS[provider][2] == "subscription"
    return False


def list_providers() -> list[ProviderSpec]:
    return [ProviderSpec(k, *v) for k, v in PROVIDERS.items()]