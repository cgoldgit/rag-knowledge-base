"""MySQL 数据库连接管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# 数据库连接字符串（含 utf8mb4 中文支持）
DATABASE_URL = (
    f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
    f"?charset=utf8mb4"
)

# 连接池：企业级配置——预先建立连接、自动回收闲置连接
engine = create_engine(
    DATABASE_URL,
    pool_size=10,          # 连接池最多同时保持 10 个连接
    max_overflow=20,       # 高峰时最多额外增加 20 个
    pool_pre_ping=True,    # 使用前检查连接是否有效（防断连）
    pool_recycle=3600,     # 连接每 1 小时自动刷新
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """每个请求获取一个数据库会话，用完自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
