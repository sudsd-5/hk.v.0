"""
5号同学：意图分析官 (LLM_Logic)

任务：编写 Prompt 让 AI 区分评论意图——"询价"(price inquiry) 与"闲聊"(casual chat)。

职责：
  1. 接收评论文本，调用大模型进行意图分类。
  2. 返回结构化 JSON，供 6 号调度员决策是否触发回复。

接口协议：
  输入 → 评论文本 (str)
  输出 → { "intent": "询价"|"闲聊", "confidence": 0.0~1.0, "reason": "...", "suggested_reply": "..." }

依赖：
  - openai>=1.0 (可选；未安装时自动降级为关键字规则引擎)
  - pydantic>=2.0 用于数据校验
"""

import json
import logging
import os
from typing import Dict, Optional

from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------------------
# 延迟导入：openai 为可选依赖，未安装时自动降级为关键字规则引擎
# ---------------------------------------------------------------------------

_openai_available = False
try:
    from openai import OpenAI  # noqa: F811

    _openai_available = True
except ImportError:  # pragma: no cover
    pass

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic 数据模型 —— 严格遵守项目 JSON 协议风格
# ---------------------------------------------------------------------------


class IntentResult(BaseModel):
    """意图分析结果，下游(6号)据此判断是否需要触发回复"""

    intent: str = Field(
        ...,
        description="意图标签：'询价' 表示用户可能在问价格、求联系方式等商业线索；'闲聊' 表示普通互动",
        pattern=r"^(询价|闲聊)$",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="置信度 0~1，供调度员设置回复阈值",
    )
    reason: str = Field(
        default="",
        description="简短中文判断依据，方便调试与日志审计",
    )
    suggested_reply: str = Field(
        default="",
        description="AI 建议的回复话术（仅询价时非空），直接可填入协议B的 payload.reply_text",
    )


# ---------------------------------------------------------------------------
# 核心 Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
你是一个短视频评论意图分析专家，负责判断观众评论是否属于"询价"意图。

## 你的任务
阅读用户评论，将其归类为以下两类之一：

1. **询价**：用户表现出购买意向、询问价格、求联系方式、咨询产品/服务详情。
   - 典型关键词：多少钱、价格、怎么卖、111、私信、加微信、联系方式、报价、求购、怎么买、来一套。
   - 即使表达很简短（如仅一个"111"），只要包含购买暗示即归此类。

2. **闲聊**：普通互动、夸赞、吐槽、无关话题、表情刷屏、打招呼等。
   - 典型示例：来了、好看、支持、厉害、哈哈哈、第一、打卡。

## 输出格式
你必须**只返回**一个合法的 JSON 对象，禁止任何额外文字或 markdown 标记：

{
  "intent": "询价" | "闲聊",
  "confidence": 0.0 到 1.0 之间的小数,
  "reason": "一句简短中文说明",
  "suggested_reply": "假如是询价则给出一条自然、拟人化的回复话术，闲聊回复留空字符串"
}

## 回复话术要求（仅询价）
- 语气自然、亲切，不要像机器模板。
- 引导用户私信或进一步沟通，例如"私信您了""后台联系我""价格私您"。
- 20字以内，简洁有力。
"""


# ---------------------------------------------------------------------------
# LLM 调用封装
# ---------------------------------------------------------------------------


def _call_llm(
    user_text: str,
    *,
    api_key: str,
    base_url: Optional[str] = None,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.0,
    max_tokens: int = 256,
    timeout: float = 15.0,
) -> str:
    """
    调用 OpenAI 兼容接口，返回模型原始文本输出。

    通过 base_url 参数可切换至 DeepSeek 等兼容提供商：
        base_url="https://api.deepseek.com"
    """

    if not _openai_available:
        raise RuntimeError("openai 库未安装，无法调用 LLM；请执行 pip install openai")

    client_kwargs: Dict[str, object] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)  # type: ignore[arg-type]

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请分析以下评论：\n{user_text}"},
        ],
    )

    raw = response.choices[0].message.content
    if raw is None:
        raise RuntimeError("LLM 返回空内容")
    return raw.strip()


# ---------------------------------------------------------------------------
# 结果解析
# ---------------------------------------------------------------------------


def _parse_result(raw: str) -> IntentResult:
    """解析 LLM 原始输出为 IntentResult，内置容错"""

    # 去除可能的 markdown 代码块标记
    cleaned = raw
    for fence in ("```json", "```"):
        cleaned = cleaned.replace(fence, "")
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM 返回非标准 JSON，尝试模糊匹配 → %s", raw[:120])
        # 兜底：基于关键字做一个规则判断
        return _keyword_fallback(raw)

    try:
        return IntentResult(**data)
    except ValidationError as exc:
        logger.warning("Pydantic 校验失败: %s，原始输出: %s", exc, raw[:120])
        # 如果 intent 字段缺失但 data 里有内容，尝试修复
        return _keyword_fallback(raw)


def _keyword_fallback(text: str) -> IntentResult:
    """
    关键字兜底 —— 当 LLM 返回格式异常时，用规则保证系统不中断。
    这不是主力逻辑，而是保险丝。
    """

    inquiry_keywords = [
        "多少钱", "价格", "报价", "怎么卖", "怎么买",
        "111", "私信", "私我", "加微信", "联系方式",
        "求购", "来一套", "链接", "上车",
    ]
    lowered = text.lower()
    is_inquiry = any(kw in lowered for kw in inquiry_keywords)

    if is_inquiry:
        return IntentResult(
            intent="询价",
            confidence=0.6,
            reason="关键字兜底匹配",
            suggested_reply="私信您了",
        )
    return IntentResult(
        intent="闲聊",
        confidence=0.7,
        reason="关键字兜底匹配",
        suggested_reply="",
    )


# ---------------------------------------------------------------------------
# 公共接口 —— 供 6 号调度员调用
# ---------------------------------------------------------------------------


def analyze_intent(
    text: str,
    *,
    api_key: str = "",
    base_url: Optional[str] = None,
    model: str = "gpt-3.5-turbo",
) -> IntentResult:
    """
    分析一条评论的意图。

    参数
    ----
    text : str
        评论文本（来自协议A的 comments[].content）
    api_key : str
        OpenAI / DeepSeek API Key，默认从环境变量 LLM_API_KEY 读取
    base_url : str | None
        兼容 OpenAI 格式的 API 地址，留空使用 OpenAI 官方
    model : str
        模型名，默认为 gpt-3.5-turbo（成本低、速度快）

    返回
    ----
    IntentResult
        结构化意图分析结果
    """

    resolved_key = api_key or os.getenv("LLM_API_KEY", "")
    if not resolved_key or not _openai_available:
        # 无 API Key 或 openai 未安装时降级为纯关键字规则
        if not _openai_available:
            logger.warning("openai 库未安装，降级为关键字规则引擎")
        else:
            logger.warning("未配置 LLM_API_KEY，降级为关键字规则引擎")
        return _keyword_fallback(text)

    try:
        raw = _call_llm(
            text,
            api_key=resolved_key,
            base_url=base_url,
            model=model,
        )
        return _parse_result(raw)
    except Exception as exc:
        logger.error("LLM 调用异常: %s，降级为关键字规则", exc)
        return _keyword_fallback(text)
