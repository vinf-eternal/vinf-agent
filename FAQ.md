# 常见问题（FAQ）

## 模型兼容

### Q1. 支持哪些模型？
**所有 OpenAI 兼容 API 都支持**——本项目的 LLM 客户端（`llm.py`）走标准 `chat/completions` 协议 + urllib，无任何厂商绑定。已验证可行的模型系：

| 模型 | 兼容 | 说明 |
|------|------|------|
| OpenAI（gpt-4o / gpt-4o-mini） | ✅ | 默认首选，`OPENAI_API_KEY` 直连 |
| DeepSeek | ✅ | `base_url` 换为 `https://api.deepseek.com/v1` |
| 通义千问 / 文心 / Moonshot 等 | ✅ | 各家兼容 OpenAI 协议的 v1 端点均可 |
| Ollama 本地模型 | ✅ | `base_url = http://127.0.0.1:11434/v1`，零外网依赖 |

### Q2. 怎么切换模型？
命令行参数优先级最高，其次环境变量，最后 `config.example` 模板：

```bash
# CLI 参数（临时切换，优先级最高）
python run.py --config config --model deepseek-chat --base-url https://api.deepseek.com/v1 --api-key sk-xxx

# 环境变量（持久切换，可写入 .env / 系统环境）
set VINF_MODEL=deepseek-chat
set VINF_BASE_URL=https://api.deepseek.com/v1
set VINF_API_KEY=sk-xxx
```

> **模型 = 外网耗材**：更换不影响本地规则、记忆、双层循环架构，随时可换。

### Q3. 没有 API key 能跑吗？
能启动、能看界面，但对话不可用。系统在缺失 key 时会明确报 `MissingApiKeyError`，提示你补 `--api-key` 或 `VINF_API_KEY`，不会静默失败。

## 跨局域网访问

### Q4. 手机 / 另一台电脑能访问 Web 界面吗？
**默认不行，这是设计决定**。Web 版默认 `--host 127.0.0.1`，只监听本机回环地址——API key 留在本机，外部设备无法触碰。

若确实需要局域网访问（如局域网内的开发测试机）：

```bash
python run.py --config config --web --host 0.0.0.0 --port 8787
```

⚠️ **安全提示**：
- 绑定 `0.0.0.0` 后，**局域网内任何设备**都可访问对话界面（包括工具调用），等同把你的本地环境暴露给同网段
- 本开源版无鉴权、无 TLS，**不要直接暴露到公网 / 映射端口**（不满足 M33 双层势垒的内核隔离要求）
- 生产 / 长期使用请保持 `127.0.0.1`，仅在临时开发场景用 `0.0.0.0`

### Q5. 默认端口是多少？
`8787`。改端口：`--port 8787` 或环境变量 `VINF_PORT`。

## 记忆持久化策略

### Q6. 记忆存在哪里？重启会丢吗？
**存在本地 `memory/` 目录（B_in 内核隔离区），跨会话、跨重启持久保存**。Vinf 的长期记忆是文件，不依赖模型会话窗口。

- 每条记忆 = `memory/` 下独立 `.md` 文件（标题即文件名）
- 会话结束后，对话本身不保留（模型无状态），但写入的记忆永久留存
- 读取时全部 `.md` 按文件名排序拼接，注入系统提示词

### Q7. 记忆怎么写入？
走**工具白名单**：Vinf 在对话中主动调用 `memory_write`（含「记忆规则」引导的价值判断——这条是否值得永久保存？）。用户输入不会绕过工具直接写入记忆（M33 内外隔离）。

手工写入同样有效：直接向 `memory/` 目录新增/编辑 `.md` 文件即可，下一次会话读取时生效。

### Q8. 记忆会被垃圾信息污染吗？
默认 `value_judge` 全部放行（开源版裁剪，不内置价值模型）。请在 `config.example/global/agents.md` 的「记忆规则」里写清楚**什么值得存、什么要丢弃**，让 Vinf 按你的标准自我把关。

### Q9. 记忆膨胀了怎么办？
- 直接删除 / 归档 `memory/` 下的过期 `.md` 文件（文件系统就是记忆管理器）
- 建议在「记忆规则」中约定定期整理周期（如每周归档过期信息、提炼长期规律）
- 暂无自动压缩机制（超范围，未落地）

### Q10. 多项目之间记忆隔离吗？
**不隔离**（当前版本）。开源版 `memory/` 是单目录、全局共享；项目级差异靠 `config/project/agents.md` 的「项目上下文」约束。多项目记忆隔离属蓝图（待开发）。

## Skill 系统

### Q11. 什么是 Skill？怎么用 Agent 创建自己的 Skill？

**Skill 是一个 Markdown 指令包**：一段描述 + 一段规则，注入系统提示词后让 Vinf 在对话中「自动切换工作方式」。它不是代码、不执行任意命令，只是可开关的行为模板（对齐 pi 的 SKILL.md 机制）。

Skill 的物理形态很简单——一个目录下的 `SKILL.md`：

```markdown
---
name: my_skill
description: 一句话说明这个 skill 什么时候用
---

# 技能正文
这里写具体的行为规则，可含步骤、输出格式、边界
```

**启动时用 `--skill-dir` 指定加载目录**（默认 `<config>/skills`），`--list-skills` 可查看已加载项：

```bash
python run.py --config config --skill-dir skills --list-skills
```

---

**下面演示如何不写一行代码，让 Vinf 帮你创建「自动化流程类」的 skill**（以「每周项目周报自动汇总」为例，非角色扮演类）。

#### 案例：让 Agent 创建「周报自动化」skill

**第 1 步：直接对 Vinf 提需求**（自然语言描述你要什么流程）：

```
请帮我创建一个名为 weekly_report 的 skill：
每周五下午自动做三件事——
1. 读取 memory 里本周的记录，按「完成/进行中/阻塞」分类
2. 生成一份周报草稿：本周进展、下周计划、待决策事项
3. 提醒我把草稿发给团队

skill 的触发条件写成：用户说"生成周报"或"周末了"时启用。
```

**第 2 步：Vinf 会生成 skill 内容**（它按记忆规则 + 你的描述组织），示意如下：

```markdown
---
name: weekly_report
description: 每周项目周报自动汇总。用户说"生成周报"或"周末了"时启用。
---

# 周报自动化流程

## 触发词
- "生成周报" / "周末了" / "周五了"

## 执行步骤
1. 检索 memory/ 中本周（周一至今）的所有记录
2. 按三类归类：✅ 完成 / 🔄 进行中 / ⛔ 阻塞
3. 生成周报草稿：
   - 本周进展：列出已完成项
   - 下周计划：进行中项的下一步
   - 待决策：阻塞项 + 需要团队拍板的问题
4. 以"周报草稿已生成"结束，提醒用户核对并发送

## 输出格式
- 标题：`第 X 周周报（MM.DD - MM.DD）`
- 三类清单，每项一行，含来源记忆文件名

## 边界
- 只汇总 memory 里已存在的记录，不凭空编造进展
- 需要外部数据（如 git 提交）时提示用户手动补充
```

**第 3 步：把内容保存为 skill 文件**（路径任意，示例 `skills/weekly_report/SKILL.md`）：

```bash
mkdir -p skills/weekly_report
# 将上面内容粘贴保存为 skills/weekly_report/SKILL.md
```

> 提示：你也可以让 Vinf 调用 `memory_write` 把生成的 skill 内容存进记忆，再自己复制到文件——更省事。

**第 4 步：重启加载并验证**：

```bash
python run.py --config config --skill-dir skills --list-skills
# 应看到  + weekly_report  描述: 每周项目周报自动汇总...
```

**第 5 步：生效**——再次对话时输入「生成周报」，Vinf 就会按该 skill 的三步流程输出周报草稿。

#### 进阶：套用「自动化工厂」模式（CrewAI Flow 风格）

> 模式来源：**望易「自动化技能工厂」**（`~/.config/opencode/skills/wangyi/execution/自动化工厂-CrewAI架构.md`）。
> 该模式把 Agent 分成「**角色工厂**」与「**自动化工厂**」两类：角色工厂固化「谁来干」（translator/engineer/tester…），自动化工厂固化「怎么干」（Flow 状态机：步骤 → 依赖 → 输入/输出 → 触发）。

开源版 Vinf 不内置多 Agent 编排（C-02：同基座多 Agent 互审不产生认知增量），但**自动化工厂的 Flow 结构完全可移植到单个 skill 里**——让 Vinf 把流程写成「带步骤依赖与输入输出的执行图」，一次对话按图执行：

```markdown
---
name: weekly_report_flow
description: 周报自动化流水线（Flow 版）。用户说"生成周报"时启用。
---

# 周报 Flow

## 触发
- 用户说"生成周报" / "周末了"

## 步骤
| # | 步骤 | 输入 | 输出 | 依赖 |
|---|------|------|------|------|
| 1 | 收集 | 本周起止日期 | raw_records[]（memory 中的本周记录） | — |
| 2 | 分类 | raw_records[] | buckets{done, in_progress, blocked} | [1] |
| 3 | 生成草稿 | buckets | draft（周报 markdown） | [2] |
| 4 | 交付 | draft | 提醒用户核对并发送 | [3] |

## 步骤 1 · 收集
- 计算本周一至今天
- 读 memory/ 全部 .md，过滤时间戳在本周内的记录
- 输出数组 `raw_records`（含来源文件名）

## 步骤 2 · 分类
- 按内容打标：完成 / 进行中 / 阻塞（无法判断的归入"待确认"）
- 输出三个桶 + 待确认项

## 步骤 3 · 生成草稿
- 标题：`第 X 周周报（MM.DD - MM.DD）`
- 三节：本周进展 / 下周计划 / 待决策
- 每项一行，附来源记忆文件名

## 步骤 4 · 交付
- 输出完整草稿，末尾一行："周报草稿已生成，请核对后发送"

## 护栏
- 任一前置步骤失败（如无本周记录）→ 停止并说明原因，不生成空草稿
- 只汇总已存在的记忆，不虚构进展
```

**两种写法的取舍**：

| 写法 | 适用 | 特点 |
|------|------|------|
| 线性步骤版（上一节） | 简单、一次性流程 | 读起来直观，写起来快 |
| Flow 表格式（本节） | 步骤多、有依赖、要复用 | 显式声明依赖与输入输出，Vinf 不易跳步或漏步 |

让 Agent 生成哪一版，直接在需求里说即可：「用自动化工厂的 Flow 风格写」。仓库已内置 `skills/weekly_report/`（线性版）供你 `--list-skills` 验证。

#### Skill 编写要点（自动化流程类）

| 要点 | 说明 |
|------|------|
| **description 必须写** | 没有 description 的文件不会被视为 skill（`skills.py` 直接跳过） |
| **触发条件写进 description** | 让 Vinf 知道「什么时候该用」 |
| **步骤要可执行** | 每一步都是它已有能力（读记忆 / 分类 / 生成文本），不写它做不到的事 |
| **给边界** | 明确「不做什么」，避免越权行为（如不凭空编造、不直接发送外部消息） |
| **保持短小** | 一段 skill 只解决一个场景，几十行即可，不要写成一本书 |

> **Skill 不是安全边界**：开源版 skill 只是注入系统提示词的文本规则（B_out 配置层），不执行任意代码。真正隔离记忆的仍是 M33 双层势垒（memory 写入只走工具白名单）。给 skill 写「可直接调用 memory_write 任意写入」这类越权指令没有实际效果，也不建议。

## 订阅型厂商（OAuth）

### Q12. 用 Kimi Code / MiniMax / GLM 这类订阅，key 过期了怎么办？

订阅型厂商（Kimi Code、MiniMax、GLM/Z.AI、OpenCode、Qwen Token Plan、GitHub Copilot、OpenAI Codex）签发的 key 是**短期 OAuth token**，几小时到几天就过期。三种接法：

**① 内置 OAuth 登录（kimi-coding，推荐）**——一次性登录，token 过期自动刷新：

```bash
python run.py --login kimi-coding
# 浏览器打开授权页 → 输入验证码 → 登录成功，凭据存到 ~/.vinf/credentials/
# 之后直接启动即用，无需任何 key 参数
python run.py --config config --provider kimi-coding
```

- 凭据文件：`~/.vinf/credentials/<provider>.json`（含 access/refresh/过期时间）
- 每次请求前自动检测：过期则用 refresh token 刷新并落盘（对齐 pi 的 `getApiKey` 机制）
- `--logout kimi-coding` 删除凭据；`--credential-dir <目录>` 自定义凭据位置
- 支持 OAuth 的厂商只有 kimi-coding（其余订阅厂商无公开 OAuth client_id）

**② 命令动态刷新（所有订阅厂商通用）**——每次请求前执行一条命令输出 key：

```bash
# 例：从某个脚本/服务拿最新 token
python run.py --config config --provider minimax --api-key-cmd "python get_token.py"
```

`--api-key-cmd` 对齐 pi 的 `getApiKey`：每轮对话请求前执行，命令 stdout 的第一行即 key，无需静态 key 也能启动。

**③ 静态 key**（DeepSeek 官方这类按量计费适用）——传统方式：

```bash
python run.py --config config --provider deepseek --api-key sk-xxx
```

**DeepSeek 官方是唯一按量计费（静态 key）的主流 Coding 厂商**，其余 kimi/minimax/glm/opencode 等订阅厂商走 ① 或 ②。

> 厂商列表与计费模式：`python run.py --list-providers`。

---

*FAQ 版本: 1.1 | 与 v0.3.1 代码行为一致 | 新增 Skill 创建演示、OAuth 订阅登录、自动化工厂 Flow 模式*
