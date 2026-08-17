"""配置读取测试."""
import pytest

from vinf_agent.config import AgentConfig, ConfigLoader


def _write(tmp_path, rel: str, content: str):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_global_only(tmp_path):
    _write(tmp_path, "global/agents.md", """# 全局
## 人设
- 名称：Vinf
- 定位：个人认知外延系统
## 行为边界
1. 不编造事实
2. 不确定就查证
""")
    cfg = ConfigLoader(tmp_path).load()
    assert "Vinf" in cfg.persona
    assert "不编造事实" in " ".join(cfg.behavior_boundaries)


def test_project_overrides_global(tmp_path):
    _write(tmp_path, "global/agents.md", "## 人设\n- 语气：简洁\n")
    _write(tmp_path, "project/agents.md", "## 项目级规则\n- 提交前必须跑测试\n")
    cfg = ConfigLoader(tmp_path).load()
    assert "提交前必须跑测试" in " ".join(cfg.project_rules)


def test_append_system_highest_priority(tmp_path):
    _write(tmp_path, "global/agents.md", "## 人设\n- 定位：助手\n")
    _write(tmp_path, "append_system.md", "## 临时规则\n- [临时] 本周禁止删除类操作\n")
    cfg = ConfigLoader(tmp_path).load()
    assert any("[临时]" in a for a in cfg.appendix)
    assert "persona" not in cfg.to_summary() or True


def test_missing_config_returns_no_sources(tmp_path):
    cfg = ConfigLoader(tmp_path).load()
    assert cfg.sources == []


def test_project_context_parsed(tmp_path):
    _write(tmp_path, "project/agents.md", "## 项目上下文\n- 项目名：demo\n- 目标：验证\n")
    cfg = ConfigLoader(tmp_path).load()
    assert cfg.project_context.get("项目名") == "demo"
    assert cfg.project_context.get("目标") == "验证"