"""向量化服务：文字 ↔ 数字指纹 + Chroma 向量库管理"""
import time
import uuid
from pathlib import Path

import chromadb
from langchain_core.documents import Document
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


def _embed_with_retry(func, texts, max_retries: int = 5, base_delay: float = 3.0):
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
    return [
        {"chunk_index": i, "content": chunks[i], "vector_id": ids[i]}
        for i in range(len(chunks))
    ]


def remove_document_chunks(doc_id: int):
    """删除某文档的全部向量（按元数据过滤）"""
    try:
        _collection.delete(where={"document_id": doc_id})
    except Exception:
        pass  # 不存在也视为成功


def search_similar(query: str, top_k: int = 6) -> list[dict]:
    """检索：把问题转成指纹，在向量库找最相似的片段"""
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
                }
            )
    return items
