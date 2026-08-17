"""RFC 8628 设备码授权流（零依赖 urllib 实现）— 对齐 pi 的 kimi-coding OAuth.

订阅型厂商（Kimi Code 等）的 key 是短期 OAuth access token。本模块提供：

1. device_login()  — 设备码登录：打印验证码 → 用户浏览器授权 → 轮询取 token
2. build_oauth_key_resolver() — 对齐 pi getApiKey：每次请求前取 key，
   过期自动用 refresh_token 刷新（401/403 视为凭据失效返回空，交给调用方降级）
3. 凭据持久化到 <credential_dir>/<provider>.json（含 access/refresh/expires）

内置厂商配置在 OAUTH_PROVIDERS；未内置的订阅厂商（minimax/glm 等）
无公开 OAuth 配置，仍走 --api-key-cmd 手动刷新。
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable

# Kimi Code 官方公开 client_id（pi 源码同步）
KIMI_CLIENT_ID = "17e5f671-d194-4dfb-9706-5516cb48c098"
DEFAULT_OAUTH_HOST = "https://auth.kimi.com"
DEFAULT_POLL_INTERVAL_SECONDS = 5
DEVICE_CODE_TIMEOUT_SECONDS = 15 * 60
MIN_REFRESH_BUDGET_SECONDS = 60  # access token 剩余寿命 < 此值视为过期，提前刷新

# provider → OAuth 配置
OAUTH_PROVIDERS: dict[str, dict[str, Any]] = {
    "kimi-coding": {
        "name": "Kimi Code (subscription)",
        "client_id": KIMI_CLIENT_ID,
        "host": lambda: (
            os.environ.get("KIMI_OAUTH_HOST")
            or os.environ.get("KIMI_CODE_OAUTH_HOST")
            or DEFAULT_OAUTH_HOST
        ),
    },
}


def supported_oauth_providers() -> list[str]:
    return list(OAUTH_PROVIDERS)


def is_oauth_supported(provider: str) -> bool:
    return provider in OAUTH_PROVIDERS


@dataclass
class OAuthToken:
    access: str
    refresh: str
    expires_at: float  # epoch seconds

    @property
    def is_expired(self) -> bool:
        return self.expires_at - time.time() < MIN_REFRESH_BUDGET_SECONDS


def default_credential_dir() -> Path:
    return Path(os.environ.get("VINF_CREDENTIAL_DIR", "~/.vinf/credentials")).expanduser()


def credential_path(provider: str, credential_dir: Path) -> Path:
    return credential_dir / f"{provider}.json"


def load_credential(provider: str, credential_dir: Path | None = None) -> OAuthToken | None:
    path = credential_path(provider, credential_dir or default_credential_dir())
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return OAuthToken(
            access=data["access"],
            refresh=data["refresh"],
            expires_at=float(data["expires_at"]),
        )
    except (OSError, KeyError, TypeError, ValueError):
        return None


def save_credential(provider: str, token: OAuthToken, credential_dir: Path | None = None) -> Path:
    d = credential_dir or default_credential_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = credential_path(provider, d)
    path.write_text(
        json.dumps(asdict(token), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def clear_credential(provider: str, credential_dir: Path | None = None) -> bool:
    path = credential_path(provider, credential_dir or default_credential_dir())
    if path.is_file():
        path.unlink()
        return True
    return False


def _oauth_host(provider: str) -> str:
    return str(OAUTH_PROVIDERS[provider]["host"]()).rstrip("/")


def _post_json(url: str, fields: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    """application/x-www-form-urlencoded POST，返回 JSON 响应."""
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"_http_status": e.code, "_body": body}
    except urllib.error.URLError as e:
        return {"_urlerror": str(e.reason)}


def _parse_token(data: dict[str, Any], ctx: str) -> OAuthToken:
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    expires_in = data.get("expires_in")
    if not access or not refresh or not isinstance(expires_in, (int, float)) or expires_in <= 0:
        raise OAuthError(f"{ctx} token 响应缺字段: {data}")
    return OAuthToken(
        access=str(access),
        refresh=str(refresh),
        expires_at=time.time() + float(expires_in),
    )


class OAuthError(Exception):
    pass


def _start_device_authorization(provider: str) -> dict[str, Any]:
    host = _oauth_host(provider)
    client_id = OAUTH_PROVIDERS[provider]["client_id"]
    data = _post_json(
        f"{host}/api/oauth/device_authorization",
        {"client_id": client_id},
    )
    required = ("device_code", "user_code", "verification_uri", "verification_uri_complete")
    if not all(isinstance(data.get(k), str) for k in required):
        raise OAuthError(f"设备授权响应无效: {data}")
    return data


def device_login(
    provider: str,
    open_browser: bool = True,
    credential_dir: Path | None = None,
    timeout_seconds: float | None = None,
) -> OAuthToken:
    """执行设备码登录流程（对齐 pi loginKimiCoding），登录成功后落盘凭据.

    打印验证码与授权 URL → 等待用户在浏览器授权 → 轮询 /api/oauth/token。
    authorization_pending 继续轮询，slow_down 增加间隔，超时/拒绝抛 OAuthError。
    """
    if provider not in OAUTH_PROVIDERS:
        raise OAuthError(f"provider {provider!r} 未内置 OAuth（内置: {list(OAUTH_PROVIDERS)}）")
    host = _oauth_host(provider)
    client_id = OAUTH_PROVIDERS[provider]["client_id"]
    device = _start_device_authorization(provider)

    user_code = device["user_code"]
    verify_url = device["verification_uri_complete"]
    print(f"\n=== {OAUTH_PROVIDERS[provider]['name']} 登录 ===")
    print(f"验证码: {user_code}")
    print(f"请在浏览器打开: {verify_url}")
    if open_browser:
        try:
            webbrowser.open(verify_url)
        except Exception:  # noqa: BLE001
            pass

    interval = float(device.get("interval") or DEFAULT_POLL_INTERVAL_SECONDS)
    expires_in = float(device.get("expires_in") or DEVICE_CODE_TIMEOUT_SECONDS)
    deadline = time.time() + (timeout_seconds or expires_in)
    token_url = f"{host}/api/oauth/token"

    print(f"等待授权（{expires_in:.0f}s 内完成，Ctrl+C 取消）...")
    while time.time() < deadline:
        time.sleep(max(interval, 1.0))
        data = _post_json(
            token_url,
            {
                "client_id": client_id,
                "device_code": device["device_code"],
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
        )
        if data.get("access_token"):
            token = _parse_token(data, "poll")
            save_credential(provider, token, credential_dir)
            return token
        error = data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5.0
            continue
        if error == "expired_token":
            raise OAuthError("设备授权已过期，请重新发起登录。")
        if error == "access_denied":
            raise OAuthError("用户拒绝授权。")
        if error:
            raise OAuthError(f"轮询失败 (error={error}){(':' + str(data.get('error_description'))) if data.get('error_description') else ''}")

    raise OAuthError("设备码授权超时，请重新发起登录。")


def refresh_token(provider: str, token: OAuthToken, credential_dir: Path | None = None) -> OAuthToken:
    """用 refresh_token 换新 token，成功落盘；401/403 视为凭据失效抛 OAuthError."""
    if provider not in OAUTH_PROVIDERS:
        raise OAuthError(f"provider {provider!r} 未内置 OAuth")
    host = _oauth_host(provider)
    client_id = OAUTH_PROVIDERS[provider]["client_id"]
    data = _post_json(
        f"{host}/api/oauth/token",
        {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": token.refresh,
        },
    )
    if data.get("access_token"):
        new = _parse_token(data, "refresh")
        save_credential(provider, new, credential_dir)
        return new
    error = data.get("error")
    status = data.get("_http_status")
    if status in (401, 403) or error == "invalid_grant":
        raise OAuthError(f"凭据已失效（{status or error}），请重新执行 --login 登录。")
    if data.get("_urlerror"):
        raise OAuthError(f"刷新失败: 网络错误 {data['_urlerror']}")
    raise OAuthError(f"刷新失败 (status={status or '?'}, error={error})")


def build_oauth_key_resolver(
    provider: str,
    credential_dir: Path | None = None,
    on_refresh: Callable[[OAuthToken], None] | None = None,
) -> Callable[[], str]:
    """对齐 pi getApiKey 的 key 解析器：每次请求前取 key.

    - access 未过期 → 直接返回
    - access 过期 → refresh_token 刷新并落盘，返回新 access
    - 刷新失败 → 返回空字符串（调用方降级到静态 api_key）
    """
    d = credential_dir or default_credential_dir()

    def resolve() -> str:
        token = load_credential(provider, d)
        if token is None:
            return ""
        if not token.is_expired:
            return token.access
        try:
            new = refresh_token(provider, token, d)
            if on_refresh:
                on_refresh(new)
            return new.access
        except OAuthError:
            return ""

    return resolve