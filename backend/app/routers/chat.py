"""问答接口：处理用户提问，返回回答和引用来源"""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Conversation, Message
from ..schemas.conversation import ChatRequest, ChatResponse
from ..deps import get_current_user
from ..services import rag_service

router = APIRouter(prefix="/api/chat", tags=["问答"])


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


@router.post("", response_model=ChatResponse, summary="发送问题并获取回答")
def chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """问答主流程：保存问题 → RAG 检索生成 → 保存回答和引用"""
    conv = _get_owned_conversation(data.conversation_id, user, db)

    # 1. 保存用户问题
    user_msg = Message(conversation_id=conv.id, role="user", content=data.message)
    db.add(user_msg)
    db.commit()

    # 2. 加载历史 + RAG 生成回答
    history = _load_history(db, conv.id)
    answer, sources = rag_service.generate_answer(data.message, history)

    # 3. 保存回答和引用来源（JSON）
    sources_json = json.dumps(sources, ensure_ascii=False)
    assistant_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=answer,
        sources=sources_json,
    )
    db.add(assistant_msg)

    # 4. 自动更新会话标题（如果还是默认的"新对话"）
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
    conv = _get_owned_conversation(data.conversation_id, user, db)

    # 1. 保存用户问题
    user_msg = Message(conversation_id=conv.id, role="user", content=data.message)
    db.add(user_msg)
    db.commit()

    # 2. 加载历史 + 流式生成
    history = _load_history(db, conv.id)
    stream, sources = rag_service.stream_answer(data.message, history)

    # 3. 拼装 SSE 输出（先发引用，再流式发内容）
    sources_json = json.dumps(sources, ensure_ascii=False)
    full_answer = [""]  # 用列表容器，让生成器内部可以填充

    def save_answer(content: str):
        """流结束后保存完整回答（用独立会话，避免连接关闭问题）"""
        from ..database import SessionLocal

        with SessionLocal() as db2:
            assistant_msg = Message(
                conversation_id=conv.id,
                role="assistant",
                content=content,
                sources=sources_json,
            )
            db2.add(assistant_msg)
            if conv.title == "新对话":
                conv.title = data.message[:20]
            db2.commit()

    def event_generator():
        # 先发送引用来源（前端先展示"正在引用"）
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources}, ensure_ascii=False)}\n\n"
        # 再流式发送回答内容
        for chunk in stream:
            if chunk:
                full_answer[0] += chunk
                yield f"data: {json.dumps({'type': 'content', 'delta': chunk}, ensure_ascii=False)}\n\n"
        # 最后发送完成标记
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
        # 流结束后保存完整回答
        save_answer(full_answer[0])

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
