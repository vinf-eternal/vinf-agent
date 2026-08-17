# Vinf Agent · 个人认知外延系统（开源版）

> **定位**：V∞ 体系开源版——零代码门槛、纯文本配置、单机自治的个人认知外延 Agent。
> **一句话**：把你的方法论编译成一套跨模型可复现的本地规则，模型只是外网耗材，规则才是你的本地主权。

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 这是什么

Vinf Agent 是 V∞ 体系的**开源版**落地。它不承诺「智能涌现」，只做一件事：

> **把「你想让 Agent 记住并遵守的规则」写成你可以看到、可以修改、可以版本管理的本地文件，不依赖模型会话记忆。**

这意味着：
- 换任意模型，规则不变（方法论与模型解耦）；
- 你的记忆、人设、行为边界都在本地，外网不可见（数据主权在本地）；
- 你 fork 一份配置，就获得一份可复现的认知外延（零代码门槛）。

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/vinf-eternal/vinf-agent.git
cd vinf-agent

# 2. 复制配置模板
cp -r config.example config

# 3. 安装（src 布局）
pip install -e .

# 4. 配置你的 API key（模型 = 外网耗材，随意更换）
#   编辑 config/global/agents.md 设置人设、记忆规则、行为边界

# 5. 运行（CLI）
python -m vinf_agent --config config

# 6. 运行（本地 Web 版）——自托管，浏览器连 localhost
python -m vinf_agent --config config --web --port 8787
# 打开 http://127.0.0.1:8787
```

> 需要 Python 3.10+。测试：`python -m pytest tests`（32 tests）。

## 目录结构

```
vinf-agent/
├── README.md              # 本文件
├── docs/
│   ├── ARCHITECTURE.md    # 设计架构图（单黑盒拓扑 + 双层循环）
│   ├── DUAL_LOOP.md       # 双层循环详解（外环交互 + 内环工具）
│   └── AUDIT.md           # 设计审计记录
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
│       ├── __main__.py    # CLI 入口（--config / --web）
│       ├── agent_loop.py  # 双层循环内核
│       ├── bootstrap.py   # 组件装配（CLI/Web 共享）
│       ├── web.py         # 本地 Web 版（stdlib http.server）
│       ├── web/index.html # 单 HTML 聊天页（无 CDN）
│       ├── config.py      # 三层配置读取 + append_system
│       ├── memory_gate.py # B_in 记忆读写门
│       ├── filter.py      # B_out 外层过滤
│       ├── tools.py       # 工具白名单
│       └── llm.py         # OpenAI 兼容客户端
└── tests/                 # 32 tests
```

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
| P3 | skills 目录加载 | 未落地 |
| 蓝图 | npm/TypeScript 重写（浏览器原生） | 蓝图 |

## 许可证

MIT。内核方法论属于你，代码属于社区。

---

*本文档版本: 0.1 | 开发态 | 设计审计通过（docs/AUDIT.md）*
