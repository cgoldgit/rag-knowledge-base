"""考题：缓存服务（Redis 读写、限流，全部用替身不连真 Redis）"""
import json

from app.services import cache


class FakeRedis:
    """假的 Redis 替身：记录操作，不真连服务"""

    def __init__(self):
        self.store = {}
        self.expirations = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, seconds, value):
        self.store[key] = value
        self.expirations[key] = seconds

    def incr(self, key):
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, key, seconds):
        self.expirations[key] = seconds


def _install_fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(cache, "_redis", fake)
    return fake


class TestGetCache:
    def test_命中缓存返回解析后的数据(self, monkeypatch):
        fake = _install_fake_redis(monkeypatch)
        fake.store["q:1"] = json.dumps({"answer": "你好"}, ensure_ascii=False)
        assert cache.get_cache("q:1") == {"answer": "你好"}

    def test_未命中返回None(self, monkeypatch):
        _install_fake_redis(monkeypatch)
        assert cache.get_cache("q:不存在") is None

    def test_存储损坏时返回None不报错(self, monkeypatch):
        fake = _install_fake_redis(monkeypatch)
        fake.store["bad"] = "{不是JSON"
        assert cache.get_cache("bad") is None

    def test_Redis故障时返回None(self, monkeypatch):
        class BrokenRedis:
            def get(self, key):
                raise ConnectionError("连接失败")

        monkeypatch.setattr(cache, "_redis", BrokenRedis())
        assert cache.get_cache("q:1") is None


class TestSetCache:
    def test_写入带默认5分钟过期(self, monkeypatch):
        fake = _install_fake_redis(monkeypatch)
        cache.set_cache("q:1", {"answer": "你好"})
        assert json.loads(fake.store["q:1"]) == {"answer": "你好"}
        assert fake.expirations["q:1"] == 300

    def test_自定义过期时间(self, monkeypatch):
        fake = _install_fake_redis(monkeypatch)
        cache.set_cache("q:1", "值", expire_seconds=60)
        assert fake.expirations["q:1"] == 60

    def test_Redis故障时不抛异常(self, monkeypatch):
        class BrokenRedis:
            def setex(self, key, seconds, value):
                raise ConnectionError("连接失败")

        monkeypatch.setattr(cache, "_redis", BrokenRedis())
        cache.set_cache("q:1", "值")  # 不应抛错


class TestRateLimit:
    def test_窗口内第一次放行(self, monkeypatch):
        fake = _install_fake_redis(monkeypatch)
        assert cache.rate_limit("user:1", limit=5) is True
        assert fake.expirations["user:1"] == 60  # 首次调用设置过期时间

    def test_未超限放行(self, monkeypatch):
        fake = _install_fake_redis(monkeypatch)
        for _ in range(5):
            assert cache.rate_limit("user:1", limit=5) is True

    def test_超限拒绝(self, monkeypatch):
        _install_fake_redis(monkeypatch)
        for _ in range(5):
            cache.rate_limit("user:1", limit=5)
        assert cache.rate_limit("user:1", limit=5) is False

    def test_Redis故障时放行不阻塞业务(self, monkeypatch):
        class BrokenRedis:
            def incr(self, key):
                raise ConnectionError("连接失败")

        monkeypatch.setattr(cache, "_redis", BrokenRedis())
        assert cache.rate_limit("user:1", limit=5) is True
