"""OAuth 设备码登录（RFC 8628）测试 — 全部 mock 网络，不触网."""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vinf_agent.oauth import (
    OAuthError,
    OAUTH_PROVIDERS,
    build_oauth_key_resolver,
    clear_credential,
    credential_path,
    default_credential_dir,
    device_login,
    is_oauth_supported,
    load_credential,
    refresh_token,
    save_credential,
    supported_oauth_providers,
    OAuthToken,
)

KIMI = "kimi-coding"


def _fake_poster(monkeypatch, responses):
    """按调用次序返回 responses 列表；最后一项耗尽后循环返回."""

    calls = {"n": 0}

    def fake(url, fields, timeout=30):
        i = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[i]

    monkeypatch.setattr("vinf_agent.oauth._post_json", fake)


def _device_response(**overrides):
    base = {
        "device_code": "dc_1",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://auth.kimi.com/verify",
        "verification_uri_complete": "https://auth.kimi.com/verify?code=ABCD-EFGH",
        "interval": 1,
        "expires_in": 60,
    }
    base.update(overrides)
    return base


def _token_response(access="acc_1", refresh="ref_1", expires_in=3600):
    return {"access_token": access, "refresh_token": refresh, "expires_in": expires_in}


def test_supported_oauth_providers_contains_kimi():
    assert "kimi-coding" in supported_oauth_providers()
    assert is_oauth_supported("kimi-coding")
    assert not is_oauth_supported("minimax")


def test_credential_path_and_default_dir(monkeypatch):
    monkeypatch.delenv("VINF_CREDENTIAL_DIR", raising=False)
    d = default_credential_dir()
    assert d.name == "credentials"
    assert credential_path("kimi-coding", d).name == "kimi-coding.json"


def test_save_and_load_credential(tmp_path):
    token = OAuthToken(access="a", refresh="r", expires_at=12345.0)
    save_credential(KIMI, token, tmp_path)
    loaded = load_credential(KIMI, tmp_path)
    assert loaded is not None
    assert loaded.access == "a"
    assert loaded.refresh == "r"
    assert loaded.expires_at == 12345.0
    assert (tmp_path / "kimi-coding.json").is_file()


def test_load_credential_missing(tmp_path):
    assert load_credential(KIMI, tmp_path) is None


def test_load_credential_corrupt(tmp_path):
    (tmp_path / "kimi-coding.json").write_text("{broken", encoding="utf-8")
    assert load_credential(KIMI, tmp_path) is None


def test_clear_credential(tmp_path):
    save_credential(KIMI, OAuthToken("a", "r", 1.0), tmp_path)
    assert clear_credential(KIMI, tmp_path) is True
    assert clear_credential(KIMI, tmp_path) is False


def test_token_is_expired():
    assert OAuthToken("a", "r", time.time() - 10).is_expired is True
    assert OAuthToken("a", "r", time.time() + 100000).is_expired is False


def test_device_login_success(monkeypatch, tmp_path):
    _fake_poster(monkeypatch, [_device_response(), _token_response()])
    monkeypatch.setattr("vinf_agent.oauth.webbrowser.open", lambda url: True)
    token = device_login(KIMI, open_browser=True, credential_dir=tmp_path)
    assert token.access == "acc_1"
    assert token.refresh == "ref_1"
    loaded = load_credential(KIMI, tmp_path)
    assert loaded is not None and loaded.access == "acc_1"


def test_device_login_pending_then_success(monkeypatch, tmp_path):
    _fake_poster(
        monkeypatch,
        [
            _device_response(),
            {"error": "authorization_pending"},
            {"error": "authorization_pending"},
            _token_response(access="acc_2"),
        ],
    )
    monkeypatch.setattr("vinf_agent.oauth.webbrowser.open", lambda url: True)
    token = device_login(KIMI, open_browser=False, credential_dir=tmp_path)
    assert token.access == "acc_2"


def test_device_login_slow_down_interval(monkeypatch, tmp_path):
    _fake_poster(
        monkeypatch,
        [_device_response(), {"error": "slow_down", "interval": 3}, _token_response()],
    )
    token = device_login(KIMI, open_browser=False, credential_dir=tmp_path)
    assert token.access == "acc_1"


def test_device_login_access_denied(monkeypatch, tmp_path):
    _fake_poster(monkeypatch, [_device_response(), {"error": "access_denied"}])
    with pytest.raises(OAuthError, match="拒绝授权"):
        device_login(KIMI, open_browser=False, credential_dir=tmp_path)


def test_device_login_expired(monkeypatch, tmp_path):
    _fake_poster(monkeypatch, [_device_response(), {"error": "expired_token"}])
    with pytest.raises(OAuthError, match="过期"):
        device_login(KIMI, open_browser=False, credential_dir=tmp_path)


def test_device_login_timeout(monkeypatch, tmp_path):
    _fake_poster(
        monkeypatch,
        [_device_response(expires_in=0.1), {"error": "authorization_pending"}],
    )
    monkeypatch.setattr("vinf_agent.oauth.time.sleep", lambda s: None)
    with pytest.raises(OAuthError, match="超时"):
        device_login(KIMI, open_browser=False, credential_dir=tmp_path)


def test_device_login_unsupported_provider(tmp_path):
    with pytest.raises(OAuthError, match="未内置"):
        device_login("minimax", open_browser=False, credential_dir=tmp_path)


def test_refresh_token_success(monkeypatch, tmp_path):
    _fake_poster(monkeypatch, [_token_response(access="new_acc", refresh="new_ref")])
    old = OAuthToken(access="old", refresh="old_ref", expires_at=time.time() - 1)
    new = refresh_token(KIMI, old, tmp_path)
    assert new.access == "new_acc"
    assert new.refresh == "new_ref"
    assert load_credential(KIMI, tmp_path).access == "new_acc"


def test_refresh_token_unauthorized(monkeypatch, tmp_path):
    _fake_poster(monkeypatch, [{"error": "invalid_grant", "_http_status": 400}])
    old = OAuthToken(access="old", refresh="old_ref", expires_at=time.time() - 1)
    with pytest.raises(OAuthError, match="失效"):
        refresh_token(KIMI, old, tmp_path)


def test_build_oauth_key_resolver_unexpired(monkeypatch, tmp_path):
    save_credential(KIMI, OAuthToken("acc_ok", "r", time.time() + 9999), tmp_path)
    resolve = build_oauth_key_resolver(KIMI, tmp_path)
    assert resolve() == "acc_ok"


def test_build_oauth_key_resolver_expired_refreshes(monkeypatch, tmp_path):
    save_credential(KIMI, OAuthToken("acc_old", "ref_x", time.time() - 5), tmp_path)
    _fake_poster(monkeypatch, [_token_response(access="acc_fresh")])
    resolve = build_oauth_key_resolver(KIMI, tmp_path)
    assert resolve() == "acc_fresh"
    assert load_credential(KIMI, tmp_path).access == "acc_fresh"


def test_build_oauth_key_resolver_refresh_fails_returns_empty(monkeypatch, tmp_path):
    save_credential(KIMI, OAuthToken("acc_old", "ref_x", time.time() - 5), tmp_path)
    _fake_poster(monkeypatch, [{"error": "invalid_grant", "_http_status": 400}])
    resolve = build_oauth_key_resolver(KIMI, tmp_path)
    assert resolve() == ""


def test_build_oauth_key_resolver_no_credential(tmp_path):
    resolve = build_oauth_key_resolver(KIMI, tmp_path)
    assert resolve() == ""