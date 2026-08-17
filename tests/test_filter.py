"""外层过滤（B_out）测试."""
from vinf_agent.filter import OuterFilter


def test_truncate_over_limit():
    f = OuterFilter(max_len=10)
    out = f.filter("x" * 100)
    assert len(out) <= 10 + len("[截断：输入超过上限]") + 1  # +\n
    assert f.is_over_limit("x" * 100)


def test_sensitive_words():
    f = OuterFilter(sensitive_words=["禁词"])
    assert "***" in f.filter("这里有个禁词")
    assert "禁词" not in f.filter("这里有个禁词")


def test_normal_pass_through():
    f = OuterFilter(max_len=100)
    text = "普通输入"
    assert f.filter(text) == text