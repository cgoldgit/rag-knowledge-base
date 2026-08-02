"""会话管理接口：每个用户管理自己的独立会话"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Conversation, Message
from ..schemas.conversation import (
    ConversationCreate, ConversationRename, ConversationOut, MessageOut,
)
from ..deps import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["会话"])


def _conv_out(c: Conversation) -> ConversationOut:
    return ConversationOut(
        id=c.id, title=c.title,
        created_at=c.created_at.isoformat(), updated_at=c.updated_at.isoformat(),
    )


@router.get("", response_model=list[ConversationOut], summary="获取我的会话列表")
def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回当前用户的所有会话（新的在前）"""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [_conv_out(c) for c in convs]


@router.post("", response_model=ConversationOut, summary="新建会话")
def create_conversation(
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = Conversation(user_id=user.id, title=data.title or "新对话")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _conv_out(conv)


def _get_owned_conversation(conv_id: int, user: User, db: Session) -> Conversation:
    """找到属于当前用户的会话（防越权访问他人会话）"""
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return conv


@router.get("/{conv_id}/messages", response_model=list[MessageOut], summary="获取会话消息记录")
def list_messages(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取某会话的全部历史消息（按时间顺序）"""
    conv = _get_owned_conversation(conv_id, user, db)
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.id.asc())
        .all()
    )
    return [
        MessageOut(
            id=m.id, conversation_id=m.conversation_id, role=m.role,
            content=m.content, sources=m.sources, created_at=m.created_at.isoformat(),
        )
        for m in msgs
    ]


@router.put("/{conv_id}", response_model=ConversationOut, summary="重命名会话")
def rename_conversation(
    conv_id: int,
    data: ConversationRename,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = _get_owned_conversation(conv_id, user, db)
    conv.title = data.title
    db.commit()
    db.refresh(conv)
    return _conv_out(conv)


@router.delete("/{conv_id}", summary="删除会话")
def delete_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除会话及其全部消息（级联删除）"""
    conv = _get_owned_conversation(conv_id, user, db)
    db.delete(conv)
    db.commit()
    return {"message": "会话已删除"}
