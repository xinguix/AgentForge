from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from .plan import Plan

class TaskCreate(BaseModel):
    """创建人物的请求体"""
    message: str  #用户问题
    system_prompt: Optional[str] = None

class TaskResponse(BaseModel):
    """返回给前端的任务详情"""
    id: str
    status: str
    input: str
    output: Optional[str]
    plan_data: Optional[Plan]
    current_step_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}