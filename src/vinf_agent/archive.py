"""对话/任务档案室：每次对话或任务自动落档，带 record_id + 时间戳.

对齐 local_lab `artifacts/expXXX_<ts>/` 实验档案风格：
  <config>/archive/sess_<epoch>/        ← 一次会话 = 一个档案目录
    session.json     会话元数据（record_id / 起止时间 / 模型 / 厂商 / 回合数）
    turns.jsonl      每回合一条 JSONL（turn_id / ts / iso / 输入 / 输出 / 工具调用 / 路由命中）
    summary.json     会话摘要（工具调用统计 / 路由命中统计 / 平均耗时）

用途：
  - 回溯：任意 record_id → 完整决策链（输入→工具→输出）
  - 进度：跨会话对比，复盘改量（科学来自无数失败实验的复盘）
  - 审计：C_ij 决策链留档，供后续 LossyPreservation 记忆回收
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

SESSION_PREFIX = "sess_"


@dataclass
class TurnRecord:
    """一次回合（一次对话/一个任务步）的完整记录."""

    turn_id: str            # 回合 ID：<session_id>_t<seq>
    ts: float               # epoch 秒
    iso: str                # ISO8601 时间戳（人类可读）
    user_input: str         # 用户输入
    response: str           # 最终回复
    stop_reason: str = ""   # end_turn | length | tool_use | error | aborted
    model: str = ""         # 模型名（外网耗材标识）
    routes_hit: list = field(default_factory=list)   # 命中的路由 target
    tool_calls: list = field(default_factory=list)   # [{name, arguments, ok, output}]
    extra: dict = field(default_factory=dict)        # 预留扩展


@dataclass
class SessionRecord:
    """一次会话的元数据."""

    session_id: str         # sess_<epoch>
    record_id: str          # UUID（全局唯一，回溯定位）
    started_at: float       # epoch
    started_iso: str
    ended_at: float | None = None
    ended_iso: str | None = None
    model: str = ""
    provider: str = ""
    config_sources: list = field(default_factory=list)
    turn_count: int = 0


class SessionArchive:
    """单会话档案：创建目录 → 追加回合 → 终结写摘要."""

    def __init__(self, root: Path, model: str = "", provider: str = ""):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.session = SessionRecord(
            session_id="",
            record_id=str(uuid.uuid4()),
            started_at=time.time(),
            started_iso=time.strftime("%Y-%m-%d %H:%M:%S"),
            model=model,
            provider=provider,
        )
        # 对齐 expXXX_<ts>：sess_<epoch>，同秒冲突则递增后缀
        base = self.root / f"{SESSION_PREFIX}{int(self.session.started_at)}"
        self.dir = base
        n = 1
        while self.dir.exists():
            self.dir = self.root / f"{SESSION_PREFIX}{int(self.session.started_at)}_{n}"
            n += 1
        self.dir.mkdir()
        self.session.session_id = self.dir.name
        self._turns_path = self.dir / "turns.jsonl"
        self._turn_seq = 0
        self._write_session()

    # ---- 写入 ---------------------------------------------------------

    def _write_session(self) -> None:
        (self.dir / "session.json").write_text(
            json.dumps(asdict(self.session), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_turn(self, turn: TurnRecord) -> None:
        """追加一条回合记录（JSONL 追加写，崩溃不丢已落盘数据）."""
        if not turn.turn_id:
            self._turn_seq += 1
            turn.turn_id = f"{self.session.session_id}_t{self._turn_seq}"
        turn.iso = turn.iso or time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(turn.ts))
        with self._turns_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(turn), ensure_ascii=False) + "\n")
        self.session.turn_count += 1

    def finalize(self) -> Path:
        """会话终结：写 summary.json，返回 summary 路径."""
        self.session.ended_at = time.time()
        self.session.ended_iso = time.strftime("%Y-%m-%d %H:%M:%S")
        self._write_session()
        summary = self._build_summary()
        path = self.dir / "summary.json"
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # ---- 读取 ---------------------------------------------------------

    def read_turns(self) -> list[dict]:
        """读取全部回合记录（回溯用）."""
        if not self._turns_path.is_file():
            return []
        out = []
        for line in self._turns_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def _build_summary(self) -> dict:
        turns = self.read_turns()
        tool_stats: dict[str, int] = {}
        route_stats: dict[str, int] = {}
        tool_failures = 0
        durations = []
        for t in turns:
            for tc in t.get("tool_calls", []):
                tool_stats[tc.get("name", "?")] = tool_stats.get(tc.get("name", "?"), 0) + 1
                if not tc.get("ok", True):
                    tool_failures += 1
            for r in t.get("routes_hit", []):
                route_stats[r] = route_stats.get(r, 0) + 1
        return {
            "session_id": self.session.session_id,
            "record_id": self.session.record_id,
            "started_iso": self.session.started_iso,
            "ended_iso": self.session.ended_iso,
            "duration_sec": (
                round(self.session.ended_at - self.session.started_at, 2)
                if self.session.ended_at else None
            ),
            "turn_count": len(turns),
            "model": self.session.model,
            "provider": self.session.provider,
            "tool_calls": tool_stats,
            "tool_failures": tool_failures,
            "routes_hit": route_stats,
        }


def list_sessions(root: Path) -> list[Path]:
    """列出全部会话档案目录（按时间升序）."""
    root = Path(root)
    if not root.is_dir():
        return []
    dirs = [d for d in root.iterdir() if d.is_dir() and d.name.startswith(SESSION_PREFIX)]
    return sorted(dirs, key=lambda d: d.name)


def find_session(root: Path, session_id: str) -> Path | None:
    """按会话 ID 或 record_id 定位档案目录."""
    root = Path(root)
    if not root.is_dir():
        return None
    for d in list_sessions(root):
        if d.name == session_id:
            return d
        sess_file = d / "session.json"
        if sess_file.is_file():
            try:
                meta = json.loads(sess_file.read_text(encoding="utf-8"))
                if meta.get("record_id") == session_id:
                    return d
            except json.JSONDecodeError:
                continue
    return None