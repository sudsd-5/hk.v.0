# llm_logic.py — 意图分析模块

> **所属项目**：AI Agent 自动化视频营销系统 (MVP)  
> **负责同学**：5 号 — 意图分析官  
> **模块定位**：第三组「大脑」—— 决策与调度中心的核心推理单元

---

## 1. 模块概述

`llm_logic.py` 是自动化视频营销系统的**意图分析引擎**。它接收来自第二组（感知器）抓取的评论区原始文本，调用大语言模型（LLM）判断用户意图是「询价」还是「闲聊」，并以结构化 JSON 输出分类结果供第六组（调度员）做回复决策。

模块设计遵循**渐进增强**原则：

| 运行条件 | 行为 |
|---|---|
| `openai` 库已安装 + `LLM_API_KEY` 已配置 | 调用 OpenAI / DeepSeek 等兼容接口进行意图分析 |
| `openai` 库未安装 或 未配置 API Key | 自动降级为**关键字规则引擎**，确保系统不中断 |

---

## 2. 架构与数据流

```
第二组（评论抓取）                    第三组（本模块）                      第六组（调度员）
┌──────────────────┐     协议A      ┌───────────────────┐    IntentResult   ┌──────────────────┐
│ Fetch_Comments   │ ──────────────> │  llm_logic.py     │ ───────────────> │ Main_Orchestrator│
│ (评论列表)        │                │  analyze_intent() │                  │ (回复决策)        │
└──────────────────┘                └───────────────────┘                  └──────────────────┘
                                           │
                                    ┌──────┴──────┐
                                    │   OpenAI /   │
                                    │   DeepSeek   │
                                    └─────────────┘
```

**输入**：评论文本 (`str`)，来自协议 A 的 `comments[].content` 字段。

**输出**：`IntentResult` 对象，包含意图标签、置信度、判断依据和建议回复话术。

---

## 3. 数据模型

### IntentResult

```python
class IntentResult(BaseModel):
    intent: str          # '询价' | '闲聊'
    confidence: float    # 置信度 0.0~1.0
    reason: str          # 一句中文判断依据
    suggested_reply: str # 询价时提供回复话术，闲聊为空字符串
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `intent` | `str` | 意图标签，仅允许 `"询价"` 或 `"闲聊"` |
| `confidence` | `float` | 置信度 (0.0~1.0)，供调度员设置回复阈值 |
| `reason` | `str` | 简短中文判断依据，方便调试与日志审计 |
| `suggested_reply` | `str` | AI 建议的回复话术（仅询价时非空），可直接填入协议 B 的 `payload.reply_text` |

---

## 4. 公开 API

### `analyze_intent()`

```python
def analyze_intent(
    text: str,
    *,
    api_key: str = "",
    base_url: Optional[str] = None,
    model: str = "gpt-3.5-turbo",
) -> IntentResult:
```

**参数**

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `text` | `str` | (必填) | 评论文本，来自协议 A 的 `comments[].content` |
| `api_key` | `str` | `""` | OpenAI / DeepSeek API Key，默认从环境变量 `LLM_API_KEY` 读取 |
| `base_url` | `str \| None` | `None` | 兼容 OpenAI 格式的 API 地址。留空使用 OpenAI 官方；传 `"https://api.deepseek.com"` 可切换至 DeepSeek |
| `model` | `str` | `"gpt-3.5-turbo"` | 模型名称，默认使用成本低、速度快的 GPT-3.5 |

**返回值**：`IntentResult` 对象。

---

## 5. Prompt 设计

模块内置精心调校的 System Prompt，核心设计要点：

| 设计要素 | 说明 |
|---|---|
| **角色设定** | 「短视频评论意图分析专家」，聚焦领域缩小幻觉 |
| **二分类任务** | 明确「询价」与「闲聊」边界，附带典型关键词参考 |
| **结构化输出** | 强制要求纯 JSON 输出，禁止 Markdown 或额外文字 |
| **拟人化话术** | 要求 AI 生成自然、亲切的回复（≤20 字），避免机器模板感 |
| **短文本兼容** | 特别说明 "111" 等极短表达也属询价意图 |

---

## 6. 兜底机制

当 LLM 不可用时，模块自动降级为**关键字规则引擎**，保障系统不间断运行：

**询价关键字**：
`多少钱`、`价格`、`报价`、`怎么卖`、`怎么买`、`111`、`私信`、`私我`、`加微信`、`联系方式`、`求购`、`来一套`、`链接`、`上车`

降级逻辑触发条件：
1. `openai` 库未安装
2. 环境变量 `LLM_API_KEY` 未配置
3. LLM 调用抛出异常
4. LLM 返回格式无法解析为有效 JSON

降级时返回默认置信度：询价 `0.6`，闲聊 `0.7`——保留足够余量供调度员按阈值过滤。

---

## 7. 使用示例

### 基础调用

```python
from llm_logic import analyze_intent

# 默认从 LLM_API_KEY 环境变量读取 Key
result = analyze_intent("这个多少钱？")

print(result.intent)           # "询价"
print(result.confidence)       # 0.95
print(result.reason)           # "用户直接询问价格"
print(result.suggested_reply)  # "私信您了，价格实惠哦"
```

### 切换至 DeepSeek

```python
result = analyze_intent(
    "111",
    api_key="sk-your-deepseek-key",
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
)
```

### 无 API Key 时自动降级

```python
# 未设置 LLM_API_KEY，自动使用关键字规则引擎
result = analyze_intent("加微信聊聊")
# IntentResult(intent='询价', confidence=0.6, reason='关键字兜底匹配', suggested_reply='私信您了')
```

### 接入调度员主循环

```python
# 在 Main_Orchestrator 中的典型调用
from llm_logic import analyze_intent

for comment in new_comments:
    result = analyze_intent(comment["content"])

    if result.intent == "询价" and result.confidence >= 0.7:
        reply_text = result.suggested_reply or "私信您了"
        await skill_reply_comment(page, comment["comment_id"], reply_text)
```

---

## 8. 异常处理策略

模块采用**分层容错**设计，确保在任何异常情况下都能返回有效的 `IntentResult`：

```
analyze_intent()
    │
    ├─ [openai 未安装 / 无 API Key] → _keyword_fallback()
    │
    └─ _call_llm() 成功
        │
        └─ _parse_result()
            ├─ [JSON 解析成功 + Pydantic 校验通过] → 正常返回
            ├─ [JSON 解析失败] → _keyword_fallback()
            └─ [Pydantic 校验失败] → _keyword_fallback()
```

所有异常均通过 `logging.warning` / `logging.error` 记录，不影响主流程。

---

## 9. 依赖

| 依赖 | 版本要求 | 是否必需 | 说明 |
|---|---|---|---|
| `pydantic` | ≥ 2.0 | **必需** | 数据模型校验 |
| `openai` | ≥ 1.0 | 可选 | 未安装时自动降级为关键字规则引擎 |

---

## 10. 环境变量

| 变量名 | 说明 |
|---|---|
| `LLM_API_KEY` | OpenAI / DeepSeek 兼容 API Key。模块启动时自动读取，也可通过 `api_key` 参数显式传入 |

---

## 11. 与团队协议的对齐

| 协议 | 对齐方式 |
|---|---|
| **协议 A** (评论数据) | `analyze_intent()` 的 `text` 参数接收 `comments[].content` |
| **协议 B** (回复指令) | `IntentResult.suggested_reply` 可直接填入 `payload.reply_text` |

本模块严格遵循项目接口协议，不私自修改字段格式，确保与第二组（感知器）和第六组（调度员）的无缝对接。
