"""考题：RAG 问答服务（提示词组装逻辑）"""
from app.services import rag_service
from app.services.rag_service import SYSTEM_PROMPT, _build_prompt


def _fake_sources():
    return [
        {
            "content": "这款手机支持快充",
            "metadata": {"filename": "手机说明.txt"},
        },
        {
            "content": "支持七天无理由退货",
            "metadata": {"filename": "售后政策.txt"},
        },
    ]


def _install_fake_search(monkeypatch, sources):
    monkeypatch.setattr(rag_service.vector_store, "search_similar", lambda q, top_k=6: sources)


class TestBuildPrompt:
    def test_无历史时历史标记为无(self, monkeypatch):
        _install_fake_search(monkeypatch, [])
        prompt, sources = _build_prompt("手机多少钱", [])
        assert "（无）" in prompt
        assert sources == []

    def test_知识库为空时明确标注(self, monkeypatch):
        _install_fake_search(monkeypatch, [])
        prompt, _ = _build_prompt("手机多少钱", [])
        assert "（知识库为空）" in prompt

    def test_检索结果带来源引用(self, monkeypatch):
        _install_fake_search(monkeypatch, _fake_sources())
        prompt, sources = _build_prompt("手机怎么样", [])
        assert "片段1 来自《手机说明.txt》" in prompt
        assert "片段2 来自《售后政策.txt》" in prompt
        assert "这款手机支持快充" in prompt
        assert len(sources) == 2

    def test_对话历史角色转换(self, monkeypatch):
        _install_fake_search(monkeypatch, [])
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好！"},
        ]
        prompt, _ = _build_prompt("手机多少钱", history)
        assert "用户: 你好" in prompt
        assert "助手: 您好！" in prompt

    def test_历史只保留最近5轮(self, monkeypatch):
        _install_fake_search(monkeypatch, [])
        history = [{"role": "user", "content": f"问题{i}"} for i in range(8)]
        prompt, _ = _build_prompt("新问题", history)
        assert "问题0" not in prompt  # 最早的第 1 轮被丢弃
        assert "问题3" in prompt  # 最近 5 轮（第 4~8 轮）保留

    def test_历史内容超长被截断(self, monkeypatch):
        _install_fake_search(monkeypatch, [])
        history = [{"role": "user", "content": "长" * 500}]
        prompt, _ = _build_prompt("问题", history)
        assert "长" * 500 not in prompt  # 超 200 字的部分被截断

    def test_系统提示词包含规则(self, monkeypatch):
        _install_fake_search(monkeypatch, [])
        prompt, _ = _build_prompt("问题", [])
        assert "知识库中没有相关信息" in SYSTEM_PROMPT  # 防编造规则存在

    def test_top_k传给检索(self, monkeypatch):
        called = {}

        def fake_search(q, top_k=6):
            called["top_k"] = top_k
            return []

        monkeypatch.setattr(rag_service.vector_store, "search_similar", fake_search)
        _build_prompt("问题", [], top_k=10)
        assert called["top_k"] == 10

    def test_history为None不报错(self, monkeypatch):
        _install_fake_search(monkeypatch, [])
        prompt, _ = _build_prompt("问题", None)
        assert "（无）" in prompt


class TestGenerateAnswer:
    """一次性回答（用假的对话模型替身，不产生真实 API 调用）"""

    def test_返回回答内容与引用来源(self, monkeypatch):
        class FakeLLM:
            def invoke(self, messages):
                self.messages = messages
                return type("Resp", (), {"content": "这款手机支持快充。"})()

        fake_llm = FakeLLM()
        monkeypatch.setattr(rag_service, "_llm", fake_llm)
        sources = [
            {"content": "这款手机支持快充", "metadata": {"filename": "手机说明.txt"}},
        ]
        monkeypatch.setattr(rag_service.vector_store, "search_similar", lambda q, top_k=6: sources)
        answer, got_sources = rag_service.generate_answer("手机支持快充吗", [])
        assert answer == "这款手机支持快充。"
        assert got_sources == sources
        # 模型收到两条消息：系统提示词 + 用户问题
        assert len(fake_llm.messages) == 2
        assert fake_llm.messages[1].content == "手机支持快充吗"


class TestStreamAnswer:
    """流式回答（打字机效果）"""

    def test_流式生成逐块产出(self, monkeypatch):
        class FakeLLM:
            def stream(self, messages):
                return [type("C", (), {"content": t})() for t in ["你", "好"]]

        monkeypatch.setattr(rag_service, "_llm", FakeLLM())
        monkeypatch.setattr(rag_service.vector_store, "search_similar", lambda q, top_k=6: [])
        stream, _ = rag_service.stream_answer("问题", [])
        assert list(stream) == ["你", "好"]
