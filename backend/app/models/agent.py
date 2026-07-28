import uuid
from sqlalchemy import String, Text, DateTime, Boolean, JSON, ForeignKey, Integer
from ..core.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class Agent(Base):
    __tablename__ = 'agent'

    id: Mapped[str]= mapped_column(
        String(36),
        primary_key=True,#主键
        default=lambda: str(uuid.uuid4())
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="智能体名称"
    )

    description: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="描述"
    )

    model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="模型名，如deepseek"
    )

    system_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="系统提示词（长文本）"
    )

    tools: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="工具列表，存JSON"
    )

    knowledge_bindings: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="知识库绑定，存JSON"
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        comment="所属用户"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )