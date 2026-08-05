from typing import Optional, Dict, Any

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Integer, JSON, Float

from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from ..core.database import Base
import uuid

class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)  # 加外键和索引
    node_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="节点名")
    node_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="agent/tool/llm")  # 可选，按需
    input: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="输入")
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="输出")  # 保持Text，除非你需要JSON
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="耗时(毫秒)")  # 改用float更通用
    token_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success", comment="状态")  # 加默认值
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)