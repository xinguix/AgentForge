from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    system_prompt: Optional[str] = None #运行前端自定义系统提示词，增加灵活性
    temperature: Optional[float] = 0.7

class ChatResponse(BaseModel):
    answer: str
    model: str
    token_usage: Optional[dict] = None