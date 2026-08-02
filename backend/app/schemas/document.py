"""知识库文档数据格式"""
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str  # processing/ready/failed
    error_message: str | None
    uploaded_by: int
    created_at: str

    class Config:
        from_attributes = True
