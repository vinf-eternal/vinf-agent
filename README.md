# Vinf Agent · 个人认知外延系统（开源版）

> **定位**：V∞ 体系开源版——零代码门槛、纯文本配置、单机自治的个人认知外延 Agent。
> **一句话**：把你的方法论编译成一套跨模型可复现的本地规则，模型只是外网耗材，规则才是你的本地主权。

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/vinf-agent.svg)](https://pypi.org/project/vinf-agent/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/vinf-agent.svg)](https://pypi.org/project/vinf-agent/)

> **PyPI**: https://pypi.org/project/vinf-agent/ ｜ **GitHub**: https://github.com/vinf-eternal/vinf-agent
>
> 文档：**[FAQ](FAQ.md)**（模型兼容 / 跨局域网访问 / 记忆持久化）· **[CHANGELOG](CHANGELOG.md)**（迭代节点）

---

## 这是什么

Vinf Agent 是 V∞ 体系的**开源版**落地。它不承诺「智能涌现」，只做一件事：

> **把「你想让 Agent 记住并遵守的规则」写成你可以看到、可以修改、可以版本管理的本地文件，不依赖模型会话记忆。**

这意味着：
- 换任意模型，规则不变（方法论与模型解耦）；
- 你的记忆、人设、行为边界都在本地，外网不可见（数据主权在本地）；
- 你 fork 一份配置，就获得一份可复现的认知外延（零代码门槛）。

## 快速开始

**一行安装（推荐，体验 = `npx pi`）：**

```bash
pipx install vinf-agent        # 或：pip install vinf-agent
vinf-agent --web               # 启动本地 Web 版，浏览器开 http://127.0.0.1:8787
vinf-agent                     # 或 CLI 模式
```

**从源码运行（零安装，纯 stdlib）：**

```bash
# 1. 克隆
git clone https://github.com/vinf-eternal/vinf-agent.git
cd vinf-agent

# 2. 复制配置模板
cp -r config.example config

# 3. 配置你的 API key（模型 = 外网耗材，随意更换）
#   编辑 config/global/agents.md 设置人设、记忆规则、行为边界

# 4. 运行（无需 pip install）
python run.py --config config            # CLI 模式
python run.py --config config --web      # 本地 Web 版
```

### 一行安装（可选，体验 = `npx pi`）

把 `bin/` 加入 PATH 后，任意目录直接执行 `vinf-agent`：

```bash
# macOS / Linux
./install.sh          # 软链 bin/vinf-agent 到 ~/.local/bin

# Windows
powershell -ExecutionPolicy Bypass -File install.ps1   # 创建 %LOCALAPPDATA%\bin\vinf-agent.cmd

# 之后任意位置：
vinf-agent --web      # 启动本地 Web 版
```

> 需要 Python 3.10+（本机已装即可，项目零第三方依赖）。测试：`python -m pytest tests`（58 tests）。

## 目录结构

```
vinf-agent/
├── README.md              # 本文件
├── run.py                 # 零安装入口（python run.py）
├── install.sh             # 一键安装（macOS/Linux）
├── install.ps1            # 一键安装（Windows）
├── bin/
│   ├── vinf-agent         # PATH 启动器（POSIX）
│   └── vinf-agent.cmd     # PATH 启动器（Windows）
├── docs/
│   ├── ARCHITECTURE.md    # 设计架构图（单黑盒拓扑 + 双层循环）
│   ├── DUAL_LOOP.md       # 双层循环详解（外环交互 + 内环工具）
│   └── AUDIT.md           # 设计审计记录
├── skills/                # 内置 Skill（鬼谷子/苏格拉底/曹操）
├── plugins/               # 插件示例（MCP 桥接等）
├── config.example/
│   ├── global/
│   │   └── agents.md      # 全局常项（人设/记忆规则/行为边界）
│   ├── project/
│   │   └── agents.md      # 项目变项（按场景覆盖）
│   └── append_system.md   # 第四层热补丁（最高优先级，可选）
├── prompts/
│   └── system.md          # 系统提示词
├── src/
│   └── vinf_agent/        # 核心代码
│       ├── __main__.py    # CLI 入口（--config / --web / --skill-dir 等）
│       ├── agent_loop.py  # 双层循环内核
│       ├── bootstrap.py   # 组件装配（CLI/Web 共享）
│       ├── web.py         # 本地 Web 版（stdlib http.server）
│       ├── web/index.html # 单 HTML 聊天页（无 CDN）
│       ├── config.py      # 三层配置读取 + append_system
│       ├── memory_gate.py # B_in 记忆读写门
│       ├── filter.py      # B_out 外层过滤
│       ├── skills.py      # Skill 加载（SKILL.md + frontmatter）
│       ├── plugins.py     # 插件加载（register(api) 协议）
│       ├── mcp_client.py  # 轻量 MCP 客户端（stdio JSON-RPC）
│       ├── onboarding.py  # 首次会话用户档案引导（agents.md 账本）
│       ├── tools.py       # 工具白名单
│       └── llm.py         # OpenAI 兼容客户端
└── tests/                 # 58 tests
```

## Skill 系统（角色加载）

把 SKILL.md（含 `name` / `description` frontmatter）放进 `<config>/skills/` 子目录，启动时自动加载并注入系统提示词。仓库内置三个角色：

| Skill | 角色 | 风格 |
|-------|------|------|
| 鬼谷子 | 纵横捭阖 | 揣情摩意、先纵后横 |
| 苏格拉底 | 产婆术 | 连续追问、逼出前提 |
| 曹操 | 务实决断 | 目标优先、结果导向 |

```bash
python run.py --config config --skill-dir skills   # 加载 skills/ 目录
python run.py --list-skills                         # 列出可用 skill
```

自定义 Skill：新建 `skills/你的角色/SKILL.md`，frontmatter 写 `name` + `description`，正文写角色规则（`enable: false` 可临时禁用）。

## 插件系统 + MCP 接口

零依赖插件协议（对齐 Pi 的 `ExtensionAPI`）：插件 = `plugins/` 目录下带 `register(api)` 函数的 `.py` 文件。

```python
# plugins/my_plugin.py
from vinf_agent.tools import ToolResult

def register(api):
    def fn(args):
        return ToolResult(tool="echo", ok=True, output=args.get("text", ""))
    api.register_tool("echo", fn, description="回显")
    api.register_prompt("本会话已装载 echo 工具。")
```

- `api.register_tool(name, fn, description, parameters)` —— 注册新工具进白名单；
- `api.register_prompt(text)` —— 追加系统提示词；
- 内置示例：`plugins/mcp_bridge.py` —— 把外部 MCP 服务器（stdio + JSON-RPC 2.0，如 `@modelcontextprotocol/server-filesystem`）的工具桥接进工具白名单；
- 缺失命令的 MCP 服务器自动跳过，不影响整体启动。

```bash
python run.py --config config --plugin-dir plugins
python run.py --list-plugins                        # 列出插件与已注册工具
```

## 首次会话引导（Onboarding）

首次启动时主动向你提问 ≥5 项用户偏好（称呼 / 人格 / 技能 / 编程熟悉度 / 是否需要大白话 / 领域），写入 `global/agents.md` 的「用户档案」段，作为长期静态基线注入系统提示词（对齐望易「人格元调度 → issues 机制」）：

- **agents.md 即进度账本**：无需独立状态数据库；按字段完整性自动判定 未启动 / 断点续引导 / 已完成；
- **三态契约**：字段行缺失 → 续问；`（未填）` 占位 → 主动跳过不追问；非空 → 已完成；
- **断点续引导**：中途中断，下次启动从缺失字段继续，不重头问；
- **敏感项**（技能 / 编程熟悉度 / 领域）提示可跳过，私有内容请走 `memory/`；
- **重采**：`python run.py --restart-onboard` 全量重问覆盖。

## 配置分层（旁路由）

```
append_system.md   ← 最高优先级（跨项目热补丁）
project/agents.md  ← 项目变项（场景定制）
global/agents.md   ← 全局常项（人设/记忆/边界）
```

三层规则持续后台生效，不直接处理用户原始流量——就像网络里的**旁路由**，主链路照常，规则始终在场。

## 本地 Web 版

```
python -m vinf_agent --config config --web [--port 8787] [--host 127.0.0.1]
```

- **自托管**：仅监听 `127.0.0.1`，API key 留在本机，浏览器只连 localhost（数据主权本地）；
- **零新增依赖**：纯 stdlib `http.server` + 单 HTML 页（无 CDN、可离线）；
- **会话记忆**：同一会话多轮消息在服务端累积，私人记忆经 B_in 门读写；
- **不做公开 SaaS**：这是开源版定位（个人认知外延系统），对外宣称不承诺「智能涌现」。

## 设计原则

1. **M33 双层势垒**：用户输入走外层过滤（PublicBuffer），私人记忆走内层隔离（PrivateCore），两层读写不互通；
2. **C-01 模态上限**：全部为 md 文本 + 轻量规则引擎，不做认知涌现承诺；
3. **C-02 审计纪律**：系统自检仅做逻辑纠错；本仓库不产出「AGI/意识/认知跃迁」类表述。

## Roadmap

| 阶段 | 内容 | 落地状态 |
|------|------|---------|
| P0 | 设计文档（架构图/README/双层循环/系统提示词/append_system） | 已落地 |
| P0 | 设计审计（docs/AUDIT.md，修复 6 处） | 已落地 |
| P1 | 双层循环外环（交互循环） | 已落地 |
| P1 | 双层循环内环（工具调用 + length-stop 防残缺） | 已落地 |
| P2 | 三层配置读取 + append_system 热补丁 | 已落地 |
| P2 | 记忆读写门（B_in 隔离） | 已落地 |
| P3 | 外层过滤（B_out） | 已落地 |
| P3 | 本地 Web 版（自托管聊天界面） | 已落地 |
| P3 | skills 目录加载（鬼谷子/苏格拉底/曹操） | 已落地 |
| P3 | 插件系统（register(api) 协议） | 已落地 |
| P3 | MCP 客户端桥接（stdio JSON-RPC） | 已落地 |
| P3 | Onboarding 首次引导（agents.md 状态机账本） | 已落地 |
| P3 | 零安装入口 + 一键安装脚本 | 已落地 |
| 蓝图 | npm/TypeScript 重写（浏览器原生） | 蓝图 |
| PyPI | 发布 vinf-agent（pipx/pip 安装） | 已落地 |

## 版本矩阵（开源版 / 科研版 / 商业版）

V∞ 体系按信息发布层级（公开层 Ω=0 / 论文层 Ω=1 / 内部层 Ω≥2）分三版交付，边界对齐「理论公开，能力可控」：

| 版本 | 定位 | 功能范围 | 交付方式 |
|------|------|---------|---------|
| **开源版**（本仓库） | 个人认知外延系统·轻量 | 双层循环、三层配置 + append_system 热补丁、记忆读写门（B_in 隔离）、外层过滤（B_out）、本地 Web 版、Skill 角色加载、插件 + MCP 桥接、Onboarding 用户档案引导、零安装部署 | PyPI + GitHub 公开，MIT |
| **科研版** | 认知架构实证研究 | 三轨审计链（演绎/归纳/相变）、临界慢化检测、相变三联检测、跨域同构验证、预注册实验规范（E1-E4）、证伪熔断 | 论文 / 白皮书公开，含方法论但不含核心校准参数 |
| **商业版** | 技术捷径权交付 | 外部标定管线（rh_traversal）、领域专属 B/γ 校准、跨域标定基线、受控 POC 插件、Token/成本预算熔断 | 签约后受控交付，源码不出库 |

**三版同源**：共用同一套 V∞ 底层公理（M33 双层势垒 / C-01 模态上限 / C-02 审计纪律），开源版是科研版与商业版的工程基础；商业版与科研版在开源版之上叠加受控能力，不改动内核骨架。

## 致谢（Acknowledgements）

- **Pi**（https://pi.dev · Mario Zechner，MIT）—— 双层循环设计（外层 steering 交互循环 + 内层工具调用循环）与事件流命名（agent_start/turn_start/tool_result/turn_end/agent_end）参考自 Pi 的 `runLoop` 实现。Vinf Agent 的实现为独立 Python 代码，仅借鉴其循环语义与 length-stop 防残缺执行的工程思路。

## 联系方式

- 邮箱：wayne777@email.cn
- 微信：qmzywe666

科研版 / 商业版咨询、领域定制合作、反馈建议，欢迎通过以上方式联系。

## 许可证

MIT。内核方法论属于你，代码属于社区。

---

*本文档版本: 0.2 | v0.3.1 | skill/plugin/MCP/onboarding 已落地, 58 tests 通过*
