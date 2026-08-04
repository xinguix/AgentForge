import enum
import uuid
from typing import Optional, Any, Dict

from sqlalchemy import String, Text, DateTime, Boolean, JSON, ForeignKey, Integer, Enum as SQLEnum
from ..core.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

#定义状态枚举
class TaskStatus(str, enum.Enum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
"""
枚举：状态只能从这个里面选
好处：防止手滑写错代码
方便阅读：代码里面写TaskStatus.COMPLETED比直接写“completed”更清晰
数据库校验：如果试图存“待办”这种非法值就会直接拒绝，保证数据绝对干净
方便以后修改，以后想把“completed”改成"done"只需要改这一处
"""

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agent.id"), nullable=True)  # 可为空

   #状态字段：用Enum类型，数据库存字符串
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=TaskStatus.CREATED,
        nullable=False,
    )
    input: Mapped[str] = mapped_column(Text, nullable=True, comment="任务输入")
    output: Mapped[str] = mapped_column(Text, nullable=True, comment="任务输出")
    error: Mapped[str] = mapped_column(Text, nullable=True, comment="错误信息")

    #存储plan的JSON数据（来自planner）
    plan_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    #当前执行到第几部（用于恢复进度）
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
