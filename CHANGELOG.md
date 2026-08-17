# Changelog

本文件记录 vinf-agent 的迭代节点。格式：版本 → 日期 → 变更摘要。落地状态采用五级标签（已落地 / 待验证 / 未落地 / 蓝图 / 新名旧法）。

## [0.3.0] - 2026-08-17

### 新增
- 零安装部署：`run.py` 入口（无需 pip install，纯 stdlib）
- `bin/vinf-agent`（POSIX）+ `bin/vinf-agent.cmd`（Windows）PATH 启动器
- `install.sh` / `install.ps1` 一键安装脚本（检测 Python → 建启动器 → 加 PATH）
- 发布至 PyPI：`pipx install vinf-agent` / `pip install vinf-agent`

### 变更
- README 快速开始改为「一行安装 + 从源码运行」双路径
- 配置中的 git clone / GitHub 地址指向 `github.com/vinf-eternal/vinf-agent`

## [0.2.0] - 2026-08-17

### 新增
- 本地 Web 版：`--web` / `--port` / `--host` 子命令
- `web.py`：stdlib `http.server`，自托管仅监听 `127.0.0.1`
- `web/index.html`：单 HTML 聊天页（无 CDN、可离线）
- `bootstrap.py`：CLI / Web 共享组件装配模块
- `tests/test_web.py`：真实 HTTP 回环测试（首页 / status / chat / 工具事件 / 会话状态）

### 修复
- `agent_loop.run_turn` 增加 `events_out` 参数，事件经纯 dict 序列化（修复 Event 对象不可 JSON 序列化）

## [0.1.0] - 2026-08-17

### 新增（初始提交）
- 设计文档：`docs/ARCHITECTURE.md`（V∞-AGENT-001）、`docs/DUAL_LOOP.md`（V∞-AGENT-002）、`docs/AUDIT.md`（V∞-AGENT-003）
- 系统提示词：`prompts/system.md`（个人认知外延系统定位，无 AGI/意识/认知跃迁表述）
- 配置模板：`config.example/{global,project}/agents.md` + `append_system.md`（第四层热补丁，优先级最高）
- 双层循环内核：`agent_loop.py`（外环 steering 交互循环 + 内环工具循环，对齐 pi `runLoop` 语义）
- 三层配置读取：`config.py`（append > project > global）
- 记忆读写门：`memory_gate.py`（B_in 隔离 + 价值判断）
- 外层过滤：`filter.py`（B_out 长度上限 + 敏感词）
- 工具白名单：`tools.py`（memory_write / memory_read / exit_session）
- OpenAI 兼容客户端：`llm.py`（零依赖 urllib 实现）
- CLI 入口：`__main__.py`（`python -m vinf_agent --config config`）
- 测试：26 tests（配置 / 过滤 / 双层循环 / 记忆门 / 工具）

### 设计审计
- `docs/AUDIT.md`：发现并修复 6 处问题（A1 内环语义冲突 / A2 幻觉引用 / A3 落地标签 / A4 README 表述 / A5-A6 Roadmap 标签与状态）
