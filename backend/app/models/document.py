"""知识库文档与分块表"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class KnowledgeDocument(Base):
    """知识库文档表：记录上传的每个文档"""
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)      # 原始文件名
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)     # 服务器保存路径
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)      # pdf/docx/txt/md/xlsx
    file_size: Mapped[int] = mapped_column(Integer, default=0)              # 字节数
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)            # 分块数
    status: Mapped[str] = mapped_column(String(20), default="processing")   # processing/ready/failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """文档分块表：每个文档切成的小片段，记录向量库中的位置"""
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)             # 片段序号
    content: Mapped[str] = mapped_column(Text, nullable=False)               # 片段原文
    vector_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 向量库中的 ID

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")
