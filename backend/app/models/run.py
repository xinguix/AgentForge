from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from ..core.database import Base
import uuid

class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    node_name: Mapped[str] = mapped_column(String(50), nullable=False, comment="节点名，如 Planner")
    input: Mapped[str] = mapped_column(Text, nullable=True, comment="该节点的输入")
    output: Mapped[str] = mapped_column(Text, nullable=True, comment="该节点的输出")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True, comment="耗时毫秒")
    token_used: Mapped[int] = mapped_column(Integer, nullable=True, comment="消耗token数")
    status: Mapped[str] = mapped_column(String(20), nullable=True, comment="该节点状态")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)