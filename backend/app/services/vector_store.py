"""向量化服务：文字 ↔ 数字指纹 + Chroma 向量库管理 + 混合检索 + 重排序"""
import json
import math
import re
import time
import urllib.request
from typing import Callable

import chromadb
import jieba
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from ..config import settings

# ===== 向量化客户端（BGE-M3，通过硅基流动 API）=====
# 注意：不能传 dimensions 参数——硅基流动 API 不支持，会报参数无效
_embeddings = OpenAIEmbeddings(
    model=settings.EMBEDDING_MODEL,
    api_key=settings.SILICONFLOW_API_KEY,
    base_url=settings.SILICONFLOW_BASE_URL,
)

# ===== Chroma 客户端（本地持久化存储）=====
_client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
_collection = _client.get_or_create_collection(
    name="knowledge_base",
    metadata={"hnsw:space": "cosine"},  # 用余弦相似度衡量"意思相近"
)

# ===== 分块器（把长文档切成小片段，相邻片段留重叠保持连贯）=====
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
    separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
)

# ===== 缓存：全部片段 + 分词结果（供 BM25 关键词检索用）=====
_all_docs_cache = None  # [(id, content, metadata)]
_tokenized_cache = None  # [tokens]
_cache_checksum = None  # 片段总数，变化时刷新缓存


def _get_all_documents() -> tuple[list[tuple[str, str, dict]], list[list[str]]]:
    """获取知识库全部片段及分词结果（带缓存，文档变化时自动刷新）"""
    global _all_docs_cache, _tokenized_cache, _cache_checksum
    count = _collection.count()
    if _all_docs_cache is not None and _cache_checksum == count:
        return _all_docs_cache, _tokenized_cache

    result = _collection.get(include=["documents", "metadatas"])
    docs = []
    tokenized = []
    if result.get("ids"):
        for i, doc_id in enumerate(result["ids"]):
            docs.append((doc_id, result["documents"][i], result["metadatas"][i]))
            tokenized.append(_tokenize(result["documents"][i]))
    _all_docs_cache = docs
    _tokenized_cache = tokenized
    _cache_checksum = count
    return docs, tokenized


def _tokenize(text: str) -> list[str]:
    """分词：jieba 中文分词 + 英文单词/数字（关键词检索用）"""
    tokens = jieba.lcut(text.lower())
    # 过滤空白和单字噪音（保留有意义的词）
    return [t.strip() for t in tokens if t.strip() and len(t.strip()) > 1]


def _tfidf_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """简化 TF 评分：查询词在文档中出现的覆盖率（0~1）"""
    if not query_tokens:
        return 0.0
    doc_set = set(doc_tokens)
    matched = sum(1 for t in query_tokens if t in doc_set)
    return matched / len(query_tokens)


def _bm25_search(query: str, top_k: int) -> list[dict]:
    """关键词检索：jieba 分词 + TF 匹配（自实现，不依赖有 bug 的 rank_bm25 库）"""
    docs, tokenized = _get_all_documents()
    if not docs:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = []
    for i, (_, content, metadata) in enumerate(docs):
        score = _tfidf_score(query_tokens, tokenized[i])
        if score > 0:
            scored.append(
                {
                    "content": content,
                    "metadata": metadata,
                    "score": score,
                    "source": "bm25",  # 标记来源：关键词检索
                }
            )

    # 取分数最高的 top_k
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]


def _rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]:
    """重排序：用 BGE-reranker 精排候选片段（提高准确率）"""
    if not candidates or top_n >= len(candidates):
        return candidates

    documents = [c["content"] for c in candidates]
    body = json.dumps(
        {"model": settings.RERANK_MODEL, "query": query, "documents": documents, "top_n": top_n}
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{settings.SILICONFLOW_BASE_URL}/rerank",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        results = sorted(data.get("results", []), key=lambda r: r["relevance_score"], reverse=True)
        reranked = []
        for r in results:
            idx = r["index"]
            item = dict(candidates[idx])
            item["score"] = float(r["relevance_score"])
            item["source"] = "rerank"
            reranked.append(item)
        return reranked
    except Exception as e:
        # 重排序失败时退回原结果（不阻塞问答）
        print(f"[vector_store] 重排序失败，使用原结果: {str(e)[:80]}")
        return candidates


def _embed_with_retry(func: Callable, texts, max_retries: int = 5, base_delay: float = 3.0):
    """调用向量 API 并自动重试（应对限流/瞬时波动；间隔递增）"""
    for attempt in range(max_retries):
        try:
            return func(texts)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)  # 3s, 6s, 12s, 24s 递增
            print(f"[vector_store] 向量化调用失败，{delay:.0f}s 后重试 ({(attempt + 1)}/{max_retries}): {str(e)[:100]}")
            time.sleep(delay)


def split_text(text: str) -> list[str]:
    """把文档文本切成小片段"""
    return _splitter.split_text(text)


def add_document_chunks(
    doc_id: int, filename: str, chunks: list[str],
) -> list[dict]:
    """把文档的片段向量化并存入 Chroma，返回各片段信息"""
    global _all_docs_cache
    # 生成 Chroma 中的唯一 ID（文档ID_片段序号）
    ids = [f"doc{doc_id}_chunk{i}" for i in range(len(chunks))]
    # 记录来源，方便回答时引用
    metadatas = [
        {"document_id": doc_id, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]

    # 批量向量化（一次 API 调用处理所有片段，快且省；失败自动重试）
    embeddings = _embed_with_retry(_embeddings.embed_documents, chunks)

    # 存入 Chroma（含原文和向量）
    _collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    _all_docs_cache = None  # 文档变化，清空缓存
    return [
        {"chunk_index": i, "content": chunks[i], "vector_id": ids[i]}
        for i in range(len(chunks))
    ]


def remove_document_chunks(doc_id: int):
    """删除某文档的全部向量（按元数据过滤）"""
    global _all_docs_cache
    try:
        _collection.delete(where={"document_id": doc_id})
        _all_docs_cache = None  # 文档变化，清空缓存
    except Exception:
        pass  # 不存在也视为成功


def _vector_search(query: str, top_k: int) -> list[dict]:
    """向量检索：把问题转成指纹，在向量库找最相似的片段"""
    query_embedding = _embed_with_retry(_embeddings.embed_query, query)
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    items = []
    if results.get("documents"):
        for i, content in enumerate(results["documents"][0]):
            items.append(
                {
                    "content": content,
                    "metadata": results["metadatas"][0][i],
                    "score": 1 - results["distances"][0][i],  # 余弦距离转相似度
                    "source": "vector",
                }
            )
    return items


def search_similar(query: str, top_k: int = 6) -> list[dict]:
    """混合检索：向量检索 + 关键词检索合并 → 重排序精排 → 返回最相关片段"""
    # 1. 两种检索各取 3 倍候选（先粗筛）；向量失败时降级为纯关键词检索
    try:
        vector_results = _vector_search(query, top_k=top_k * 3)
    except Exception as e:
        print(f"[vector_store] 向量检索失败，降级为关键词检索: {str(e)[:80]}")
        vector_results = []
    bm25_results = _bm25_search(query, top_k=top_k * 3)

    # 2. 合并去重（按内容去重，优先保留向量结果）
    seen = set()
    merged = []
    for item in vector_results + bm25_results:
        key = item["content"][:100]
        if key not in seen:
            seen.add(key)
            merged.append(item)

    # 3. 重排序精排（取最终 top_k）
    return _rerank(query, merged[: top_k * 2], top_k)
