from typing import List, Dict, Optional, Any, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import operator

class AgentState(TypedDict):
    """LangGraph的全局状态"""
    #Annotated[list, operator.add]表示这个字段是累加的
    #多个节点返回的messages会自动合并（append）,而不是覆盖
    messages: Annotated[List[BaseMessage], operator.add]
    #Annotated:类型的“附加便签纸”：Annotated[类型，额外元数据]，不改变原有的类型，只是给这个类型“贴上一张附加信息的标签”

    #当前任务ID(第二周做多任务追踪时很有用
    task_id: Optional[str]

    #中间思考过程
    intermediate_steps: Optional[List[Dict[str, Any]]]