from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from ..core.database import Base
import uuid
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, comment="user / assistant / system")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    meta: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict, comment="存 token 消耗等附加信息")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)