"""知识库管理接口：仅管理员可用（上传/列表/删除/状态）"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User, KnowledgeDocument, DocumentChunk
from ..schemas.document import DocumentOut
from ..deps import require_admin
from ..services.document_parser import extract_text, UnsupportedFormatError
from ..services import vector_store

router = APIRouter(prefix="/api/kb", tags=["知识库"])

# 允许的格式
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md", "markdown", "xlsx", "xls"}


def _doc_out(d: KnowledgeDocument) -> DocumentOut:
    return DocumentOut(
        id=d.id, filename=d.filename, file_type=d.file_type,
        file_size=d.file_size, chunk_count=d.chunk_count, status=d.status,
        error_message=d.error_message, uploaded_by=d.uploaded_by,
        created_at=d.created_at.isoformat(),
    )


@router.post("/upload", response_model=DocumentOut, summary="上传文档")
async def upload_document(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """上传文档并立即处理：解析 → 分块 → 向量化 → 入库"""
    # 检查格式
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {ext}，支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 保存文件到上传目录（用唯一名防止冲突；限制 20MB 防内存溢出）
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件超过 20MB 限制")
    safe_name = f"{uuid.uuid4().hex[:12]}_{file.filename}"
    save_path = Path(settings.UPLOAD_DIR) / safe_name
    save_path.write_bytes(content)

    # 创建文档记录（状态：处理中）
    doc = KnowledgeDocument(
        filename=file.filename,
        file_path=str(save_path),
        file_type=ext,
        file_size=len(content),
        status="processing",
        uploaded_by=admin.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 处理流程：解析 → 分块 → 向量化（出错则标记失败）
    try:
        with open(save_path, "rb") as f:
            text = extract_text(file.filename, f)
        if not text:
            raise ValueError("文档内容为空，无法解析")

        chunks = vector_store.split_text(text)
        chunk_infos = vector_store.add_document_chunks(doc.id, doc.filename, chunks)

        # 保存每个片段到数据库（关联向量库位置）
        for info in chunk_infos:
            db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=info["chunk_index"],
                    content=info["content"],
                    vector_id=info["vector_id"],
                )
            )
        doc.status = "ready"
        doc.chunk_count = len(chunks)
        db.commit()
        db.refresh(doc)
    except UnsupportedFormatError as e:
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
        # 处理失败时回滚已写入的向量（防止检索命中幽灵片段）
        vector_store.remove_document_chunks(doc.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"文档处理失败: {e}")

    return _doc_out(doc)


@router.get("/documents", response_model=list[DocumentOut], summary="文档列表")
def list_documents(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """返回全部文档（新的在前）"""
    docs = (
        db.query(KnowledgeDocument)
        .order_by(KnowledgeDocument.created_at.desc())
        .all()
    )
    return [_doc_out(d) for d in docs]


@router.delete("/documents/{doc_id}", summary="删除文档")
def delete_document(
    doc_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除文档：数据库记录 + 文件 + 向量库片段"""
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

    # 删除向量库中的片段
    vector_store.remove_document_chunks(doc.id)

    # 删除服务器文件（忽略失败）
    try:
        Path(doc.file_path).unlink(missing_ok=True)
    except Exception:
        pass

    db.delete(doc)  # 级联删除分块记录
    db.commit()
    return {"message": "文档已删除"}


@router.get("/stats", summary="知识库统计")
def knowledge_base_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """统计：文档数、总片段数、各状态数量（管理员看板）"""
    total_docs = db.query(KnowledgeDocument).count()
    ready_docs = db.query(KnowledgeDocument).filter(KnowledgeDocument.status == "ready").count()
    total_chunks = (
        db.query(DocumentChunk).join(KnowledgeDocument)
        .filter(KnowledgeDocument.status == "ready").count()
    )
    return {
        "total_documents": total_docs,
        "ready_documents": ready_docs,
        "total_chunks": total_chunks,
    }
