"""考题：向量库（分块、分词、关键词评分/检索、重排序）"""
from app.services import vector_store


class TestSplitText:
    def test_长文本切成多块(self):
        text = "商品说明。" * 400  # 约 2000 字
        chunks = vector_store.split_text(text)
        assert len(chunks) > 1

    def test_短文本单块(self):
        chunks = vector_store.split_text("一个短句子。")
        assert chunks == ["一个短句子。"]

    def test_空文本返回空列表(self):
        assert vector_store.split_text("") == []

    def test_每块长度不超上限(self):
        text = "测试段落内容。" * 200
        chunks = vector_store.split_text(text)
        assert all(len(c) <= 500 for c in chunks)


class TestTokenize:
    def test_中文分词(self):
        tokens = vector_store._tokenize("苹果手机支持快充")
        assert "苹果" in tokens
        assert "手机" in tokens
        assert "快充" in tokens

    def test_过滤单字和空白(self):
        tokens = vector_store._tokenize("我 的 好手机 ")
        assert "手机" in tokens
        assert not any(len(t) <= 1 for t in tokens)
        assert "" not in tokens

    def test_英文单词保留(self):
        tokens = vector_store._tokenize("iPhone 15 price")
        assert "iphone" in tokens
        assert "price" in tokens

    def test_空文本返回空列表(self):
        assert vector_store._tokenize("") == []


class TestTfidfScore:
    def test_全覆盖得1分(self):
        assert vector_store._tfidf_score(["快充", "手机"], ["快充", "手机", "电池"]) == 1.0

    def test_部分匹配按比例得分(self):
        assert vector_store._tfidf_score(["快充", "手机"], ["快充", "屏幕"]) == 0.5

    def test_无匹配得0分(self):
        assert vector_store._tfidf_score(["快充"], ["屏幕"]) == 0.0

    def test_空查询得0分(self):
        assert vector_store._tfidf_score([], ["快充"]) == 0.0


class TestBm25Search:
    def _install_fake_docs(self, monkeypatch):
        docs = [
            ("doc1_0", "苹果手机支持快充功能", {"filename": "a.txt"}),
            ("doc2_0", "这款手机屏幕很大", {"filename": "b.txt"}),
            ("doc3_0", "蓝牙耳机续航持久", {"filename": "c.txt"}),
        ]
        tokenized = [
            vector_store._tokenize(d[1]) for d in docs
        ]
        monkeypatch.setattr(vector_store, "_get_all_documents", lambda: (docs, tokenized))

    def test_只返回匹配片段(self, monkeypatch):
        self._install_fake_docs(monkeypatch)
        results = vector_store._bm25_search("快充", top_k=6)
        assert len(results) == 1
        assert results[0]["content"] == "苹果手机支持快充功能"
        assert results[0]["source"] == "bm25"
        assert results[0]["score"] == 1.0

    def test_按相关度排序(self, monkeypatch):
        self._install_fake_docs(monkeypatch)
        # "手机" 命中两条：doc1（命中1/2词）与 doc2（命中1/2词）同分；"苹果" 只命中 doc1
        results = vector_store._bm25_search("苹果手机", top_k=6)
        assert results[0]["content"] == "苹果手机支持快充功能"
        assert len(results) == 2

    def test_top_k限制条数(self, monkeypatch):
        self._install_fake_docs(monkeypatch)
        results = vector_store._bm25_search("手机", top_k=1)
        assert len(results) == 1

    def test_空库返回空列表(self, monkeypatch):
        monkeypatch.setattr(vector_store, "_get_all_documents", lambda: ([], []))
        assert vector_store._bm25_search("手机", top_k=6) == []

    def test_无匹配返回空列表(self, monkeypatch):
        self._install_fake_docs(monkeypatch)
        assert vector_store._bm25_search("冰箱", top_k=6) == []


class TestRerank:
    def _make_candidates(self):
        return [
            {"content": "片段A", "metadata": {"filename": "a.txt"}, "score": 0.1, "source": "bm25"},
            {"content": "片段B", "metadata": {"filename": "b.txt"}, "score": 0.2, "source": "bm25"},
        ]

    def test_候选少于目标数时原样返回(self):
        cands = self._make_candidates()
        assert vector_store._rerank("查询", cands, top_n=5) == cands

    def _make_three_candidates(self):
        return [
            {"content": "片段A", "metadata": {"filename": "a.txt"}, "score": 0.1, "source": "bm25"},
            {"content": "片段B", "metadata": {"filename": "b.txt"}, "score": 0.2, "source": "bm25"},
            {"content": "片段C", "metadata": {"filename": "c.txt"}, "score": 0.3, "source": "bm25"},
        ]

    def test_重排序成功按分数排(self, monkeypatch):
        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return (
                    b'{"results": [{"index": 2, "relevance_score": 0.9},'
                    b'{"index": 0, "relevance_score": 0.5},'
                    b'{"index": 1, "relevance_score": 0.2}]}'
                )

        monkeypatch.setattr(vector_store.urllib.request, "urlopen", lambda *a, **k: FakeResp())
        result = vector_store._rerank("查询", self._make_three_candidates(), top_n=2)
        # 按相关度从高到低：片段C(0.9) → 片段A(0.5) → 片段B(0.2)
        assert [r["content"] for r in result] == ["片段C", "片段A", "片段B"]
        assert result[0]["source"] == "rerank"
        assert result[0]["score"] == 0.9

    def test_重排序失败退回原结果(self, monkeypatch):
        def boom(*args, **kwargs):
            raise Exception("网络超时")

        monkeypatch.setattr(vector_store.urllib.request, "urlopen", boom)
        cands = self._make_candidates()
        # 失败时退回原结果，但按目标数量截断（防止引用膨胀）
        result = vector_store._rerank("查询", cands, top_n=1)
        assert result == cands[:1]

    def test_空候选直接返回(self):
        assert vector_store._rerank("查询", [], top_n=3) == []
