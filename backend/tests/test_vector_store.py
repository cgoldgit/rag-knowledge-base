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


class FakeCollection:
    """假的 Chroma 集合替身：记录调用，不真连向量库"""

    def __init__(self, count=0, docs=None):
        self.count_value = count
        self.docs = docs or []  # [(id, content, metadata)]
        self.count_calls = 0
        self.get_calls = 0
        self.add_ids = None
        self.add_metas = None
        self.add_embeddings = None
        self.delete_where = None

    def count(self):
        self.count_calls += 1
        return self.count_value

    def get(self, **kwargs):
        self.get_calls += 1
        return {
            "ids": [d[0] for d in self.docs],
            "documents": [d[1] for d in self.docs],
            "metadatas": [d[2] for d in self.docs],
        }

    def add(self, ids=None, documents=None, embeddings=None, metadatas=None):
        self.add_ids = ids
        self.add_docs = documents
        self.add_embeddings = embeddings
        self.add_metas = metadatas

    def delete(self, where=None):
        self.delete_where = where


class TestGetAllDocuments:
    """片段+分词缓存的刷新逻辑（文档数量变化时自动刷新）"""

    def _reset_cache(self, monkeypatch):
        monkeypatch.setattr(vector_store, "_all_docs_cache", None)
        monkeypatch.setattr(vector_store, "_tokenized_cache", None)
        monkeypatch.setattr(vector_store, "_cache_checksum", None)

    def test_文档数不变时第二次调用不重复查询(self, monkeypatch):
        fake = FakeCollection(
            count=1,
            docs=[("d1_0", "苹果手机支持快充", {"filename": "a.txt"})],
        )
        monkeypatch.setattr(vector_store, "_collection", fake)
        self._reset_cache(monkeypatch)
        d1, _ = vector_store._get_all_documents()
        d2, _ = vector_store._get_all_documents()
        assert d1 == d2
        assert fake.get_calls == 1  # 第二次命中缓存，不再访问假集合

    def test_文档数量变化时自动刷新缓存(self, monkeypatch):
        fake = FakeCollection(
            count=1,
            docs=[("d1_0", "苹果手机支持快充", {"filename": "a.txt"})],
        )
        monkeypatch.setattr(vector_store, "_collection", fake)
        self._reset_cache(monkeypatch)
        vector_store._get_all_documents()
        # 模拟新增文档：数量变 2
        fake.count_value = 2
        fake.docs.append(("d2_0", "蓝牙耳机续航持久", {"filename": "b.txt"}))
        docs, _ = vector_store._get_all_documents()
        assert len(docs) == 2
        assert fake.get_calls == 2  # 数量变化，缓存失效重新查询


class TestSearchSimilar:
    """混合检索总入口（向量失败降级、合并去重）"""

    def test_向量检索失败降级为关键词检索(self, monkeypatch):
        def boom(query, top_k=6):
            raise Exception("向量服务不可用")

        monkeypatch.setattr(vector_store, "_vector_search", boom)
        monkeypatch.setattr(
            vector_store, "_bm25_search",
            lambda q, top_k=6: [
                {"content": "苹果手机支持快充", "metadata": {"filename": "a.txt"}, "score": 1.0, "source": "bm25"}
            ],
        )
        monkeypatch.setattr(vector_store, "_rerank", lambda q, cands, top_n: cands)
        results = vector_store.search_similar("快充", top_k=3)
        assert len(results) == 1
        assert results[0]["source"] == "bm25"

    def test_混合检索按内容合并去重(self, monkeypatch):
        vector_results = [
            {"content": "苹果手机支持快充", "metadata": {"filename": "a.txt"}, "score": 0.9, "source": "vector"},
        ]
        bm25_results = [
            {"content": "苹果手机支持快充", "metadata": {"filename": "a.txt"}, "score": 1.0, "source": "bm25"},
            {"content": "蓝牙耳机续航持久", "metadata": {"filename": "b.txt"}, "score": 0.8, "source": "bm25"},
        ]
        seen = {}

        def fake_rerank(q, cands, top_n):
            seen["cands"] = cands
            return cands

        monkeypatch.setattr(vector_store, "_vector_search", lambda q, top_k=6: vector_results)
        monkeypatch.setattr(vector_store, "_bm25_search", lambda q, top_k=6: bm25_results)
        monkeypatch.setattr(vector_store, "_rerank", fake_rerank)
        vector_store.search_similar("手机", top_k=3)
        contents = [c["content"] for c in seen["cands"]]
        # 同内容只保留一份（优先向量版），第二份来自 bm25
        assert contents == ["苹果手机支持快充", "蓝牙耳机续航持久"]

    def test_全链路重排序失败退回原结果(self, monkeypatch):
        cands = [
            {"content": f"片段{i}", "metadata": {"filename": "a.txt"}, "score": 0.1 * i, "source": "vector"}
            for i in range(1, 8)
        ]

        def boom(*args, **kwargs):
            raise Exception("网络超时")

        monkeypatch.setattr(vector_store.urllib.request, "urlopen", boom)
        monkeypatch.setattr(vector_store, "_vector_search", lambda q, top_k=6: cands)
        monkeypatch.setattr(vector_store, "_bm25_search", lambda q, top_k=6: [])
        results = vector_store.search_similar("快充", top_k=3)
        # 6 条候选 > top_n=3 触发重排序；失败后退回前 3 条原结果
        assert len(results) == 3
        assert results[0]["content"] == "片段1"


class TestAddRemoveChunks:
    """文档片段入库/删除（用假的嵌入与集合，不产生真实 API 调用）"""

    def _install_fake_store(self, monkeypatch):
        fake = FakeCollection()
        monkeypatch.setattr(vector_store, "_collection", fake)
        monkeypatch.setattr(
            vector_store, "_embeddings",
            type(
                "FakeEmbed",
                (),
                {"embed_documents": lambda self, texts: [[0.1] * 8 for _ in texts]},
            )(),
        )
        return fake

    def test_add_生成ID与元数据并存储(self, monkeypatch):
        fake = self._install_fake_store(monkeypatch)
        monkeypatch.setattr(vector_store, "_all_docs_cache", None)
        result = vector_store.add_document_chunks(
            doc_id=42, filename="说明.txt", chunks=["片段一", "片段二"]
        )
        assert len(result) == 2
        assert result[0]["vector_id"] == "doc42_chunk0"
        assert result[1]["vector_id"] == "doc42_chunk1"
        assert fake.add_ids == ["doc42_chunk0", "doc42_chunk1"]
        assert fake.add_metas[0]["document_id"] == 42
        assert fake.add_metas[0]["filename"] == "说明.txt"
        assert len(fake.add_embeddings) == 2

    def test_remove_按文档ID删除并清空缓存(self, monkeypatch):
        fake = self._install_fake_store(monkeypatch)
        monkeypatch.setattr(vector_store, "_all_docs_cache", [("x",)])
        vector_store.remove_document_chunks(doc_id=7)
        assert fake.delete_where == {"document_id": 7}
        assert vector_store._all_docs_cache is None

    def test_remove_删除失败不抛异常(self, monkeypatch):
        class FailDelete(FakeCollection):
            def delete(self, where=None):
                raise Exception("删除失败")

        monkeypatch.setattr(vector_store, "_collection", FailDelete())
        vector_store.remove_document_chunks(doc_id=7)  # 不应抛错
