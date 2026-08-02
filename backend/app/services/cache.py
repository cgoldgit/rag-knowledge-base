"""Redis 缓存服务：问答缓存 + 限流"""
import json

import redis

from ..config import settings

# Redis 连接池（企业级：连接复用）
# 注意：protocol=2 使用 RESP2 协议——本机 Redis 5.0 不支持 RESP3（HELLO 命令），
# 不加会连接失败
_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,  # 自动解码字符串
    protocol=2,  # 兼容 Redis 5.0
    max_connections=50,
)
_redis = redis.Redis(connection_pool=_pool)


def get_cache(key: str):
    """读取缓存（JSON 自动解析）"""
    try:
        val = _redis.get(key)
        return json.loads(val) if val else None
    except Exception:
        return None


def set_cache(key: str, value, expire_seconds: int = 300):
    """写入缓存（默认 5 分钟过期）"""
    try:
        _redis.setex(key, expire_seconds, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass  # 缓存失败不影响主流程


def rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """限流：同一 key 在窗口期内最多允许 limit 次；超限返回 False

    用原子 INCR 计数（首次设置过期时间），并发安全
    """
    try:
        current = _redis.incr(key)
        if current == 1:
            _redis.expire(key, window_seconds)
        return current <= limit
    except Exception:
        return True  # Redis 故障时放行（不阻塞业务）
