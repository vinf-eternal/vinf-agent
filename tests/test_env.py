"""env.py 轻量 .env 加载器测试."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import vinf_agent.env as env_mod  # noqa: E402


def test_parse_line_basic():
    assert env_mod._parse_line("KEY=value") == ("KEY", "value")
    assert env_mod._parse_line(" KEY = value ") == ("KEY", "value")
    assert env_mod._parse_line("export FOO=bar") == ("FOO", "bar")


def test_parse_line_comments_and_quotes():
    assert env_mod._parse_line("# comment") is None
    assert env_mod._parse_line("") is None
    assert env_mod._parse_line('A="hello world"') == ("A", "hello world")
    assert env_mod._parse_line("B='single'") == ("B", "single")


def test_load_dotenv_explicit(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("VINF_API_KEY=sk-test\nVINF_BASE_URL=https://example.com/v1\n", encoding="utf-8")
    # 备份并清理
    old = {k: v for k, v in sys.modules["os"].environ.items() if k in ("VINF_API_KEY", "VINF_BASE_URL")}
    for k in old:
        del sys.modules["os"].environ[k]
    try:
        loaded = env_mod.load_dotenv(explicit=str(env_file))
        assert loaded == env_file
        import os

        assert os.environ["VINF_API_KEY"] == "sk-test"
        assert os.environ["VINF_BASE_URL"] == "https://example.com/v1"
    finally:
        # 恢复
        for k in ("VINF_API_KEY", "VINF_BASE_URL"):
            sys.modules["os"].environ.pop(k, None)
        sys.modules["os"].environ.update(old)


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    import os

    monkeypatch.setenv("VINF_API_KEY", "real-env")
    env_file = tmp_path / ".env"
    env_file.write_text("VINF_API_KEY=from-file\n", encoding="utf-8")
    loaded = env_mod.load_dotenv(explicit=str(env_file))
    assert loaded == env_file
    assert os.environ["VINF_API_KEY"] == "real-env"


def test_find_dotenv_walks_up(tmp_path):
    child = tmp_path / "a" / "b"
    child.mkdir(parents=True)
    (tmp_path / ".env").write_text("X=1\n", encoding="utf-8")
    found = env_mod._find_dotenv(child)
    assert found == (tmp_path / ".env")


def test_load_dotenv_missing_explicit(tmp_path):
    assert env_mod.load_dotenv(explicit=str(tmp_path / "nope.env")) is None


def test_load_dotenv_no_file(tmp_path):
    assert env_mod.load_dotenv(start=tmp_path) is None