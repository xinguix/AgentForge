from sqlalchemy import String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from datetime import datetime
from ..core.database import Base
import uuid
from typing import Optional, Dict, Any

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    #关联原始文档
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    #元数据
    chunk_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata",JSON, nullable=True)

    #向量字段（维度512,对应bge-small-zh-v1.5模型）
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)