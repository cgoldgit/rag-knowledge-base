"""项目配置：从 .env 读取所有秘密和参数"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录（backend 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 加载根目录 .env（含 API 密钥）
load_dotenv(BASE_DIR / ".env")


class Settings:
    # ===== 数据库（MySQL）=====
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "rag_user")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "rag123456")
    MYSQL_DB = os.getenv("MYSQL_DB", "rag_kb")

    # ===== Redis =====
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    # ===== JWT 认证 =====
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 登录凭证有效期：24 小时

    # ===== DeepSeek 大模型 =====
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

    # ===== 硅基流动（向量 + 重排序）=====
    SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

    # ===== 知识库 =====
    UPLOAD_DIR = BASE_DIR / "backend" / "uploads"  # 上传文档保存目录
    CHROMA_DIR = BASE_DIR / "backend" / "chroma_data"  # 向量库存储目录
    CHUNK_SIZE = 500  # 文档分块大小（字符数）
    CHUNK_OVERLAP = 80  # 相邻分块重叠（保持上下文连贯）


settings = Settings()
