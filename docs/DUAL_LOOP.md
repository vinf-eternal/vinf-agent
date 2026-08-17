# V∞-AGENT-002｜双层循环详解

> 版本: 0.1（设计稿）｜状态: 待审计
> 参考实现：`pi-main/packages/agent/src/agent-loop.ts` `runLoop`（外层 steering/follow-up `while(true)` + 内层工具调用 `while(hasMoreToolCalls)`）
> BOUNDARY-STATEMENT v1.0：本文档描述开源版 Agent 的双层循环机制设计（SIM-E 规划层），不涉及「意识/智能/认知涌现」强语义宣称。

---

## 一、为什么是双层循环

单层循环（单次提问→单次回复）的局限：模型输出里可能出现**工具调用**，而工具执行结果需要**回填后再生成**——这是循环的。同时，用户在等待期间可能输入**新消息（steering）**，需要在下一次生成前注入——这也是循环的。

双层循环把这两种循环分开：

| 层 | 循环原因 | 终止条件 |
|----|---------|---------|
| 外环（交互） | 用户持续输入 / steering 注入 | 会话结束 / stopReason=error/aborted |
| 内环（工具） | 工具调用 → 执行 → 回填 → 再生成 | 无工具调用 / terminate=true |

> pi 实现对应：外环 `while (true)` + `config.getSteeringMessages?.()`；内环 `while (hasMoreToolCalls || pendingMessages.length > 0)`。

---

## 二、外环交互循环（伪代码）

```
def run_session(context):
    pending = collect_steering()          # 用户等待期间的输入
    while True:                           # ← 外层循环：交互
        if pending:
            inject(pending, context)      # steering 注入
            pending = []
        response = llm_call(context)      # 生成
        if response.stop_reason in (error, aborted):
            emit_turn_end(response)
            break                          # 会话结束
        # ← 进入内环
        has_more_tools = True
        while has_more_tools or pending:
            tool_calls = extract_tool_calls(response)
            if not tool_calls:
                has_more_tools = False
                continue
            if response.stop_reason == length:
                results = fail_all(tool_calls)   # 截断→全部失败，防残缺参数
            else:
                results = execute_tool_calls(tool_calls)
            backfill(results, context)
            response = llm_call(context)   # 基于回填上下文的再次生成
            has_more_tools = response 含工具调用
        yield response                     # 交给用户
        pending = collect_steering()       # 等待下一输入
```

### 外环关键点

1. **steering 注入**：用户可打断等待，输入新消息，在下次生成前注入；
2. **error/aborted 终止**：模型错误或用户中断时立即退出会话，不留半状态；
3. **每次外环迭代产出一次对用户的完整回复**（含内环工具执行后的最终生成）。

---

## 三、内环工具循环（伪代码）

```
while (hasMoreToolCalls):
    # 1. 提取工具调用
    tool_calls = [c for c in response.content if c.type == "toolCall"]

    # 2. length 截断防护
    if response.stop_reason == "length":
        tool_calls = [mark_failed(c, "truncated_args") for c in tool_calls]   # 全部失败，不执行

    # 3. 执行工具
    executed = execute_tool_calls(tool_calls)   # 支持并行；可设置 terminate 标志

    # 4. 回填上下文
    for r in executed.results:
        context.messages.append(r)

    # 5. 再次生成
    response = llm_call(context)
    has_more_tools = has_tool_calls(response) and not executed.terminate
```

### 内环关键点

1. **length-stop 防残缺执行**：模型输出被 token 上限截断时，工具参数可能残缺，全部失败而非执行——对齐 pi 的 `failToolCallsFromTruncatedMessage`；
2. **terminate 标志**：某工具（如「退出会话」）可强制终止内环；
3. **回填再生成**：工具结果是上下文的一部分，模型必须基于最新状态继续。

---

## 四、开源版裁剪范围

| 能力 | 本仓库 | 说明 |
|------|--------|------|
| 外环 + 内环 | ✅ 做 | 核心循环 |
| 并行工具执行 | ✅ 做 | 简单并行（thread pool） |
| steering 注入 | ✅ 做 | pending 消息队列 |
| 多 Agent 协作 | ❌ 不做 | 超出开源版范围 |
| 跨域实验 | ❌ 不做 | C-01 模态上限 |
| 完整三轨审计 | ❌ 不做 | 只做基础自检（演绎轨子集） |

---

## 五、状态与事件

```
状态机：
  IDLE → RUNNING(外环) → [内环循环] → READY(产出回复) → IDLE
                 ↘ error/aborted → TERMINATED

事件（对齐 pi EventStream）：
  agent_start / turn_start / message_start / message_end /
  tool_call_start / tool_result / turn_end / agent_end
```

---

*本文档版本: 0.1 | 设计稿 | 审计通过（见 AUDIT.md）*
