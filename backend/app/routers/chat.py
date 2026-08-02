"""问答接口：处理用户提问，返回回答和引用来源"""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Conversation, Message
from ..schemas.conversation import ChatRequest, ChatResponse
from ..deps import get_current_user
from ..services import rag_service, cache

router = APIRouter(prefix="/api/chat", tags=["问答"])

# 限流：每用户每分钟最多 10 次问答（防恶意刷接口）
RATE_LIMIT_PER_MINUTE = 10


def _get_owned_conversation(conv_id: int, user: User, db: Session) -> Conversation:
    """找到属于当前用户的会话（防越权）"""
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return conv


def _load_history(db: Session, conv_id: int) -> list[dict]:
    """加载最近对话历史（供多轮上下文理解）"""
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.id.desc())
        .limit(10)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(msgs)]


def _get_user_top_k(user: User) -> int:
    """读取用户设置的检索片段数（默认 6）"""
    import json

    if user.settings:
        try:
            data = json.loads(user.settings)
            return max(1, min(10, int(data.get("top_k", 6))))
        except Exception:
            pass
    return 6


@router.post("", response_model=ChatResponse, summary="发送问题并获取回答")
def chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """问答主流程：保存问题 → RAG 检索生成 → 保存回答和引用"""
    # 限流：防恶意刷接口
    if not cache.rate_limit(f"rl:chat:{user.id}", RATE_LIMIT_PER_MINUTE):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="操作太频繁，请稍后再试")

    conv = _get_owned_conversation(data.conversation_id, user, db)

    # 读取用户设置（检索片段数）
    top_k = _get_user_top_k(user)

    # 判断是否为会话的第一问（无历史 = 独立问题，可安全缓存/命中）
    is_first_question = not db.query(Message).filter(Message.conversation_id == conv.id).count()

    # 1. 尝试命中缓存（相同问题 5 分钟内秒回；仅第一问可命中，避免多轮上下文错乱）
    cache_key = f"qa:{data.message.strip()}"
    cached = cache.get_cache(cache_key) if is_first_question else None
    if cached:
        answer, sources = cached["answer"], cached["sources"]
    else:
        # 2. 加载历史 + RAG 生成回答
        history = _load_history(db, conv.id)
        answer, sources = rag_service.generate_answer(data.message, history, top_k)
        # 3. 写入缓存（仅缓存独立问题）
        if is_first_question:
            cache.set_cache(cache_key, {"answer": answer, "sources": sources}, expire_seconds=300)

    # 4. 保存用户问题
    user_msg = Message(conversation_id=conv.id, role="user", content=data.message)
    db.add(user_msg)
    db.commit()

    # 5. 保存回答和引用来源（JSON）
    sources_json = json.dumps(sources, ensure_ascii=False)
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=answer,
        sources=sources_json,
    )
    db.add(assistant_msg)

    # 6. 自动更新会话标题（如果还是默认的"新对话"）
    if conv.title == "新对话":
        conv.title = data.message[:20]
    db.commit()
    db.refresh(assistant_msg)

    return ChatResponse(
        message_id=assistant_msg.id,
        content=answer,
        sources=sources,
    )


@router.post("/stream", summary="流式问答（打字机效果）")
def chat_stream(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """流式问答：回答逐字返回，前端实时显示"""
    # 限流：防恶意刷接口
    if not cache.rate_limit(f"rl:chat:{user.id}", RATE_LIMIT_PER_MINUTE):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="操作太频繁，请稍后再试")

    conv = _get_owned_conversation(data.conversation_id, user, db)

    # 1. 保存用户问题
    user_msg = Message(conversation_id=conv.id, role="user", content=data.message)
    db.add(user_msg)
    db.commit()

    # 2. 加载历史 + 流式生成（使用用户设置的检索片段数）
    top_k = _get_user_top_k(user)
    history = _load_history(db, conv.id)
    stream, sources = rag_service.stream_answer(data.message, history, top_k)

    # 3. 拼装 SSE 输出（先发引用，再流式发内容）
    sources_json = json.dumps(sources, ensure_ascii=False)
    full_answer = [""]  # 用列表容器，让生成器内部可以填充

    def save_answer(content: str, title: str):
        """流结束后保存完整回答（用独立会话，避免连接关闭问题）"""
        from ..database import SessionLocal

        with SessionLocal() as db2:
            # 重新查询会话（避免请求会话的脏数据）
            conv2 = db2.get(Conversation, conv.id)
            assistant_msg = Message(
                conversation_id=conv.id,
                role="assistant",
                content=content,
                sources=sources_json,
            )
            db2.add(assistant_msg)
            if conv2 and conv2.title == "新对话":
                conv2.title = title
            db2.commit()

    def event_generator():
        try:
            # 先发送引用来源（前端先展示"正在引用"）
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources}, ensure_ascii=False)}\n\n"
            # 再流式发送回答内容
            for chunk in stream:
                if chunk:
                    full_answer[0] += chunk
                    yield f"data: {json.dumps({'type': 'content', 'delta': chunk}, ensure_ascii=False)}\n\n"
            # 最后发送完成标记
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        finally:
            # 无论成功/中断/异常，都保存已生成的内容（防数据丢失）
            save_answer(full_answer[0], data.message[:20])

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
