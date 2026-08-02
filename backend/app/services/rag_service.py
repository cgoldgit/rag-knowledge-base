"""RAG 问答服务：检索知识库 → 组装提示词 → 大模型生成回答"""
from typing import Iterator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..config import settings
from . import vector_store

# DeepSeek 对话模型（回答问题的"专家"）
_llm = ChatOpenAI(
    model=settings.DEEPSEEK_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    temperature=0.3,  # 低温度：回答更严谨，少发散
    max_tokens=1024,
)

# 系统提示词：要求模型只依据知识库内容回答（防止编造）
SYSTEM_PROMPT = """你是电商平台的专业客服助手，负责回答用户关于商品的问题。

规则：
1. 只依据下面提供的【知识库资料】回答问题，不要编造资料中没有的信息
2. 如果知识库资料不足以回答，明确说"知识库中没有相关信息"，不要猜测
3. 回答要简洁、准确、友好，使用中文
4. 引用资料中的关键信息时，保持原意

【知识库资料】
{context}

【对话历史】
{history}
"""

# 检索片段数（取最相关的几段）
TOP_K = 6


def _build_prompt(question: str, history: list[dict]) -> tuple[str, list[dict]]:
    """组装提示词：检索相关内容 + 拼上下文"""
    # 1. 在知识库检索相关内容
    sources = vector_store.search_similar(question, top_k=TOP_K)

    # 2. 拼装知识库资料文本
    context_parts = []
    for i, s in enumerate(sources, 1):
        context_parts.append(f"[片段{i} 来自《{s['metadata']['filename']}》]\n{s['content']}")
    context = "\n\n".join(context_parts) if context_parts else "（知识库为空）"

    # 3. 拼装对话历史（最近5轮）
    history_text = ""
    if history:
        lines = []
        for h in history[-5:]:
            role = "用户" if h["role"] == "user" else "助手"
            lines.append(f"{role}: {h['content'][:200]}")
        history_text = "\n".join(lines)

    prompt = SYSTEM_PROMPT.format(context=context, history=history_text or "（无）")
    return prompt, sources


def generate_answer(question: str, history: list[dict]) -> tuple[str, list[dict]]:
    """生成回答（一次性返回）"""
    prompt, sources = _build_prompt(question, history)
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=question),
    ]
    response = _llm.invoke(messages)
    return response.content, sources


def stream_answer(question: str, history: list[dict]) -> tuple[Iterator[str], list[dict]]:
    """流式生成回答（打字机效果，逐字返回）"""
    prompt, sources = _build_prompt(question, history)
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=question),
    ]
    stream = _llm.stream(messages)
    # 逐块产出文本
    return (chunk.content for chunk in stream), sources
