from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

#1.创建Agent时，前端传什么？（不需要传id和时间，数据库自动生成）
class AgentCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Agent名称"
    )

    description: Optional[str] = Field(
        None,
        description="描述"
    )

    model: str = Field(
        ...,
        description="模型名称，如deepseek-chat"
    )

    system_prompt: Optional[str] = Field(
        None,  #系统提示词可以是str,也可以是none
        description="系统提示词"
    )

    tools: Optional[List[str]] = Field(
        default=[],  #默认的空列表，表示工具可以传字符串列表或者none
        description="绑定的工具列表"
    )

    knowledge_bindings: Optional[list[str]] = Field(
        default=[],
        description="绑定的知识库D列表"
    )

#2.返回给前端时，包含数据库生成的字段（id,time）
class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    model: str
    system_prompt: Optional[str]
    tools: List[str]
    knowledge_bindings: List[str]
    created_at: datetime
    updated_at: datetime

    #让Pydantic自动把ORM对象转化成字典（等价于from_attributes=True）
    model_config = {"from_attributes": True}
    #ORM:（对象映射关系）就是把数据库的表翻译成python的类
    #pydantic:专门用来检验和转换数据格式的

#3.更新Agent(PATCH时可部分更新，全字段Optional)  patch(补丁)
class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None
    knowledge_bindings: Optional[List[str]] = None