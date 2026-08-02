"""后端入口：组装所有部分"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .models import User
from .security import hash_password
from .routers import auth, conversations, knowledge_base, chat

# 确保上传目录和向量库目录存在
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CHROMA_DIR).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时：建表 + 预置管理员账号"""
    Base.metadata.create_all(bind=engine)
    _seed_admin()
    yield


def _seed_admin():
    """预置管理员 admin/123456（只建一次）"""
    from sqlalchemy.orm import Session as SASession
    from .database import SessionLocal

    db: SASession = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == "admin").first()
        if not exists:
            db.add(User(username="admin", password_hash=hash_password("123456"), is_admin=True))
            db.commit()
    finally:
        db.close()


app = FastAPI(
    title="RAG 企业级知识库问答系统",
    description="基于 LangChain 的电商商品知识库问答系统",
    version="0.1.0",
    lifespan=lifespan,
)

# 跨域设置：允许前端（http://localhost:5173）访问后端
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(knowledge_base.router)
app.include_router(chat.router)


@app.get("/api/health", summary="健康检查")
def health():
    return {"status": "ok", "service": "rag-kb-backend", "version": "0.1.0"}
