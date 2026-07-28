import uuid
from sqlalchemy import String, Text, DateTime, Boolean, JSON, ForeignKey, Integer
from ..core.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id"), nullable=True)  # 可为空
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created",
                                         comment="created/running/failed/completed")
    input: Mapped[str] = mapped_column(Text, nullable=True, comment="任务输入")
    output: Mapped[str] = mapped_column(Text, nullable=True, comment="任务输出")
    error: Mapped[str] = mapped_column(Text, nullable=True, comment="错误信息")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
